from typing import Literal
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.common.exceptions import WebDriverException
import time
import pandas as pd
import os 
import re 

import warnings

##### Get the directory where this file is housed ########################
wd = os.path.dirname(__file__)
fdel= os.path.sep

def check_browser_installed():
    """Check if browsers are installed using Selenium's service checks"""
    firefox_available = False
    chrome_available = False
    
    try:
        firefox_service = FirefoxService()
        firefox_service.is_connectable()  # This checks if Firefox is available
        firefox_available = True
    except WebDriverException:
        pass

    try:
        chrome_service = ChromeService()
        chrome_service.is_connectable()  # This checks if Chrome is available
        chrome_available = True
    except WebDriverException:
        pass

    if not (firefox_available or chrome_available):
        warnings.warn(
            "Neither Firefox nor Chrome browser found. Please install one of them to use this package."
            "Firefox: https://www.mozilla.org/en-US/firefox/new/"
            "Google Chrome: https://www.google.com/chrome/ ",
            RuntimeWarning
        )
    
    return firefox_available, chrome_available

## Standalone functions  ########################################
def export_html(html: str, save_path: str = wd+fdel+'last_soup.html'):
    with open(save_path, 'w') as wp:
        wp.write(html)
    return None

def split_numeric(input_string: str):
    # Match integers or decimal numbers
    # Match numbers including metric suffixes
    if not isinstance(input_string, str):
        #print("split_numeric function: Input is not a string, returning input.")
        return input_string
    else:
        number_pattern = r'-?\d*\.?\d+[KMGBT]?'
        
        # Find the numeric part
        match = re.search(number_pattern, input_string)
        
        if match:
            numeric_part = match.group()
            # Replace the numeric part with empty string to get remainder
            non_numeric = re.sub(number_pattern, '', input_string)
            return numeric_part, non_numeric.strip()
        else:   
            return input_string

def map_frequency(diff):
    """Map timedelta to frequency string"""
    days = diff.days
    if days > 0 and days <= 3:
        return "D"
    elif days > 3 and days <= 14:
        return "W"
    elif days > 14 and days <= 60:
        return "MS"
    elif days > 60 and days <= 120:
        return "QS"
    elif days > 120 and days <= 420:
        return "AS"
    else:
        return "Multi-year"
    
# BeautifulSoup approach
def check_element_exists_bs4(soup, selector):
    try:
        element = soup.select_one(selector)
        return element.text if element else None
    except:
        return None

def convert_metric_prefix(value_str: str) -> float:
    """Convert string with metric prefix to float
    e.g., '1.3K' -> 1300, '2.6M' -> 2600000
    """
    # Dictionary of metric prefixes and their multipliers
    metric_prefixes = {
        'K': 1000,
        'M': 1000000, 
        'B': 1000000000,
        'G': 1000000000,
        'T': 1000000000000}
    
    # Clean and standardize input
    value_str = value_str.strip().upper()
    
    try:
        # Match number and prefix
        match = re.match(r'^(-?\d*\.?\d+)([KMGBT])?$', value_str)
        if match:
            number, prefix = match.groups()
            number = float(number)
            # Multiply by prefix value if present
            if prefix and prefix in metric_prefixes:
                number *= metric_prefixes[prefix]
            return number
        return float(value_str)  # No prefix case
    except:
        print(f"Error converting value: {value_str}")
        return value_str  # Return original if conversion fails
    
def ready_datestr(date_str: str):
    """Replace substrings in datestr using a dictionary to get the string ready
    for parsing to datetime. Using QS frequency convention for quarters."""
    
    quarters = {"Q1": "January",
                "Q2": "April",
                "Q3": "July",
                "Q4": "October"}

    for key, value in quarters.items():
        date_str = date_str.replace(key, value)
    return date_str
    
def normalize_series(series, new_min, new_max):
    """
    Normalize a pandas Series to a given range [new_min, new_max].

    Parameters:
    series (pd.Series): The pandas Series to normalize.
    new_min (float): The minimum value of the new range.
    new_max (float): The maximum value of the new range.

    Returns:
    pd.Series: The normalized pandas Series.
    """
    series_min = series.min()
    series_max = series.max()
    normalized_series = (series - series_min) / (series_max - series_min) * (new_max - new_min) + new_min
    return normalized_series

def invert_series(series: pd.Series, max_val: float = None):
    """
    Invert a pandas Series.

    Parameters:
    series (pd.Series): The pandas Series to invert.

    Returns:
    pd.Series: The inverted pandas Series.
    """
    if max_val is None:
        max_val = series.max()
        print(f"Max value: {max_val}, subtracting series from this value.")
    return (max_val - series) #+ series.min()

def find_zero_crossing(series):
    """Find the x-intercept (value where series crosses zero) using linear interpolation"""
    if not ((series.min() < 0) and (series.max() > 0)):
        return None
        
    # Find where values change sign
    for i in range(len(series)-1):
        if (series.iloc[i] <= 0 and series.iloc[i+1] > 0) or \
           (series.iloc[i] >= 0 and series.iloc[i+1] < 0):
            # Get x values (index values)
            x1, x2 = series.index[i], series.index[i+1]
            # Get y values
            y1, y2 = series.iloc[i], series.iloc[i+1]
            # Linear interpolation to find x-intercept
            zero_x = x1 + (0 - y1)*(x2 - x1)/(y2 - y1)
            return zero_x
            
    return None


########### Classes ##############################################################################

class get_tooltip(object):
    """Class to scrape tooltip data from a chart element using Selenium.
    This can get x, y data from the tooltip box displayed by a site such as Trading Economics when the cursor
    is moved over a chart. It can move the cursor to specific points on the chart and extract tooltip text.
    It extracts date and value data from the tooltip text.
    """

    def __init__(self, 
                    driver: webdriver = None, 
                    url: str = None,
                    chart_x: int = 600, chart_y: int = 375):
        
        """Initialize the scraper with a URL and chart coordinates
        **Parameters:**
        - driver (webdriver): A Selenium WebDriver object, can put in an active one or make a new one for a new URL.
        - url (str): The URL of the webpage to scrape. Unnecessary if driver is provided.
        - chart_x (float): The total length in pixels of the svg chart image that we are trying to scrape.
        - chart_y (float): The total height in pixels of the svg chart image that we are trying to scrape.
        """
        if driver is None:
            self.driver = webdriver.Firefox()
            self.driver.get(url)
        else:
            self.driver = driver
        self.chart_x = round(chart_x)
        self.chart_y = round(chart_y)

        self.last_url = url

        #wait for the chart element to be present
        chart_selector = '.highcharts-plot-background'
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, chart_selector))
        )

        # Locate the chart element
        self.chart_element = self.driver.find_element(By.CSS_SELECTOR, chart_selector)

        # Initialize ActionChains
        self.actions = ActionChains(self.driver)

    def move_cursor(self, x: int = 0, y: int = 0):
        self.actions.move_to_element_with_offset(self.chart_element, x, y).perform()
        print(f"Moved cursor to ({x}, {y})")
        return
                        
    def move_pointer(self, x_offset: int = None, y_offset: int = 1, x_increment: int = 1):
        """Move cursor to a specific x-offset and y-offset from the chart element.
        Uses Selenium ActionChains to move the cursor."""

        if x_offset is None:
            x = 0
            while x < self.chart_x:
                self.move_cursor(x, y_offset)
                time.sleep(1)
                if self.get_tooltip_text():
                    break
                x += x_increment
            return True
        else:
            self.move_cursor(x, y_offset)
            time.sleep(1)
            if self.get_tooltip_text():
                return True
            else:
                return False
    
    def scrape_dates_from_tooltips(self, num_points: int = 10, x_increment: int = 1):
        """Scrape first and last data points using viewport coordinates.
        Also scrape dates from the first n points to determine time series frequency.
        **Parameters:**
        - num_points (int): The number of data points to scrape in addition to first and last points.
        - x_increment (int): The number of pixels to move cursor horizontally between points.
        **Returns:**
        - data_points (list): A list of dictionaries containing scraped data points.
        - num_points (int): The number of data points scraped."""
        
        # Get chart element and viewport info
        chart_rect = self.chart_element.rect
        viewport_width = self.driver.execute_script("return window.innerWidth;")
        viewport_height = self.driver.execute_script("return window.innerHeight;")
        
        print(f"Viewport dimensions: {viewport_width} x {viewport_height}")
        print(f"Chart position in viewport: x={chart_rect['x']}, y={chart_rect['y']}")
        
        data_points = []
        i = 0
        last_date = ""
        viewport_y = chart_rect['y'] + (chart_rect['height'] / 2)
        last_x =  chart_rect['x'] + chart_rect['width']
        date_change = []
        just_run = False
        date_change_count = 0

        while len(data_points) < num_points + 2:  #scrape first 10 points and then last point...
            try: 
                # Use ActionChains to move to absolute viewport position
                actions = ActionChains(self.driver)
                if len(data_points) == num_points + 1:
                    print("Scraping the last point now at x = ", last_x)
                    x_pos = last_x
                else:
                    x_pos = chart_rect['x'] + i*x_increment

                actions.move_by_offset(x_pos, viewport_y).perform()
                actions.reset_actions()  # Reset for next move
                #print(f"Moving to point at viewport coordinates ({x_pos}, {viewport_y})")
                time.sleep(0.05)
                
                tooltip = self.get_tooltip_text()
                date, value = self.extract_date_value_tooltip(tooltip)

                if not just_run:
                    if date == last_date:
                        i += 1
                        date_change_count += 1
                        continue
                    else:   
                        date_change.append(date_change_count)
                        date_change_count = 0
                        # Here we're trying to find the average number f pixels needed to move betweeen dates from the 1st 3 points to speed up subsequent scraping.
                        if len(date_change) == 3:
                            #print("Here's the date change list: ", date_change[1::])
                            av_incs = sum(date_change[1::])/2
                            x_increment = round(av_incs)
                            just_run == True
                
                if date == last_date:
                    #print(f"Date not changed from last point, skipping: {date}")
                    i += 1
                    continue

                if tooltip and date and value:
                    #print(f"Found point data: {date}, {value}")

                    data_points.append({
                        'viewport_x': x_pos,
                        'viewport_y': viewport_y,
                        'tooltip_data': tooltip,
                        "date": date,
                        "value": value
                    })
                else:
                    print(f"No tooltip found at point")
                
                last_date = date
            except Exception as e:
                print(f"Error scraping tooltip at ({x_pos}, {viewport_y}), error: {str(e)}")
                continue
        
        return data_points, num_points
    
    def extract_date_value_tooltip(self, tooltip_element: str):
        """Extract date and value from a single tooltip HTML"""

        # try:
        # Parse tooltip HTML
        soup = BeautifulSoup(tooltip_element, 'html.parser')
        
        # Extract date and value
        date = soup.select_one('.tooltip-date').text.strip()
        date = ready_datestr(date)
        
        value = soup.select_one('.tooltip-value').text.replace(' Points', '')
        #print("Date: ", date, "Value: ", value)
        try:
            value = float(value)
        except:
            pass
        
        try:
            date = pd.to_datetime(date)
        except:
            print(f"Error converting date string: {date}")
            pass
        
        # try:
        splitted = split_numeric(value)
        if isinstance(splitted, tuple):
            value = convert_metric_prefix(splitted[0])
        else:
            value = splitted

            # except Exception as e:
            #     print(f"Error converting value string: {value}")
            #     return
            
        # except Exception as e:
        #     print(f"Error parsing tooltip data: {str(e)}")
        #     return None
    
        return date, value
        
    def scrape_chart_data(self):
        """Scrape data points by moving cursor across chart within viewport bounds
        I don't know if this is working atm, this approcach of pulling each datapoint one at a time from the tooltips
        may be implemented later yet it will need javascript implementation to work fast enough.
        Currently this is very slow when done this way. """
        
        # Get chart dimensions and position
        chart_rect = self.chart_element.rect
        chart_width = chart_rect['width']
        chart_height = chart_rect['height']
        
        # Find chart center in viewport coordinates
        chart_center_x = chart_rect['x'] + (chart_width / 2)
        chart_center_y = chart_rect['y'] + (chart_height / 2)
        print(f"Chart center: ({chart_center_x}, {chart_center_y})")
        
        # Calculate valid x-coordinate range
        x_start = chart_center_x - (chart_width / 2)  # Leftmost valid x
        x_end = chart_center_x + (chart_width / 2)    # Rightmost valid x
        
        # Initialize data collection
        data_points = []
        x_increment = 2
        
        # Move cursor left to right within valid range
        current_x = x_start

        while current_x <= x_end:
            try:
                # Calculate offset from chart center
                x_offset = current_x - chart_center_x
                
                # Move cursor using offset from center
                self.actions.move_to_element(self.chart_element)\
                        .move_by_offset(x_offset, 0)\
                        .perform()
                
                time.sleep(0.2)
                
                # Get tooltip data
                tooltip = self.get_tooltip_text()
                if tooltip:
                    data_points.append({
                        'x_position': current_x,
                        'tooltip_data': tooltip
                    })
                
                current_x += x_increment
                
            except Exception as e:
                print(f"Error at x={current_x}: {str(e)}")
                current_x += x_increment
                
        return data_points

    def get_tooltip_text(self, tooltip_selector: str = '.highcharts-tooltip'):
        """Get tooltip text from the chart element"""

        # Locate the tooltip element and extract the text
        tooltip_elements = self.driver.find_elements(By.CSS_SELECTOR, tooltip_selector)
        if tooltip_elements:
            for tooltip_element in tooltip_elements:
                tooltip_text = tooltip_element.get_attribute("outerHTML")
                #print(tooltip_text)
            return tooltip_text
        else:
            print("Tooltip not found")
            return None
    
    def bail_out(self):
        self.driver.quit()
        return None
    
class generic_webdriver(object):
    """Generic webdriver class for initializing a Selenium WebDriver"""

    # Define browser type with allowed values
    BrowserType = Literal["chrome", "firefox"]
    def __init__(self, driver: webdriver = None, 
                 browser: BrowserType = "firefox", 
                 headless: bool = True):
        
        self.browser = browser
        self.headless = headless

        if driver is None:
            if browser == "chrome":
                options = webdriver.ChromeOptions()
                if headless:
                    options.add_argument('--headless')
                self.driver = webdriver.Chrome(options=options)
            elif browser == "firefox":
                options = webdriver.FirefoxOptions()
                if headless:
                    options.add_argument('--headless')
                self.driver = webdriver.Firefox(options=options)
            else:
                raise ValueError("Unsupported browser! Use 'chrome' or 'firefox'.")
        else:
            self.driver = driver
        
        self.wait = WebDriverWait(self.driver, timeout=10)