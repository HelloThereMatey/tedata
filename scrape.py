import requests
from typing import Literal
import numpy as np
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
import time
import pandas as pd
from datetime import datetime
import time
import random
import os 

wd = os.path.dirname(__file__)
fdel= os.path.sep


## Standalone functions  ########################################
def export_html(html: str, save_path: str = wd+fdel+'last_soup.html'):
    with open(save_path, 'w') as wp:
        wp.write(html)
    return None

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

########### Classes ##############################################################################

class get_tooltip(object):
        
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
        
        def scrape_startEnd_dates(self):
            """Scrape first and last data points using viewport coordinates"""
            
            # Get chart element and viewport info
            chart_rect = self.chart_element.rect
            viewport_width = self.driver.execute_script("return window.innerWidth;")
            viewport_height = self.driver.execute_script("return window.innerHeight;")
            
            print(f"Viewport dimensions: {viewport_width} x {viewport_height}")
            print(f"Chart position in viewport: x={chart_rect['x']}, y={chart_rect['y']}")
            
            # Define viewport-relative points to check
            check_points = [
                {
                    'position': 'first',
                    'viewport_x': chart_rect['x'],  # Left edge + small offset
                    'viewport_y': chart_rect['y'] + (chart_rect['height'] / 2)
                },
                {
                    'position': 'last',
                    'viewport_x': chart_rect['x'] + chart_rect['width'],  # Right edge - small offset
                    'viewport_y': chart_rect['y'] + (chart_rect['height'] / 2)
                }
            ]
            
            data_points = []
            
            for point in check_points:
                try:
                    print(f"Moving to {point['position']} point at viewport coordinates ({point['viewport_x']}, {point['viewport_y']})")
                    
                    # Use ActionChains to move to absolute viewport position
                    actions = ActionChains(self.driver)
                    actions.move_by_offset(point['viewport_x'], point['viewport_y']).perform()
                    actions.reset_actions()  # Reset for next move
                    
                    time.sleep(1)
                    
                    tooltip = self.get_tooltip_text()
                    if tooltip:
                        print(f"Found {point['position']} point data: {tooltip}")
                        data_points.append({
                            'position': point['position'],
                            'viewport_x': point['viewport_x'],
                            'viewport_y': point['viewport_y'],
                            'tooltip_data': tooltip
                        })
                    else:
                        print(f"No tooltip found for {point['position']} point")
                        
                except Exception as e:
                    print(f"Error at {point['position']} point: {str(e)}")
                    continue
            
            return data_points

        def retry_dates(self, max_retries: int = 5):
            for i in range(max_retries):
                data_points = self.scrape_startEnd_dates()
                if len(data_points) == 2:
                    dates = self.extract_dates_from_tooltips(data_points)
                    if dates:
                        return dates
                else:
                    continue
            return None
            
        def scrape_chart_data(self):
            """Scrape data points by moving cursor across chart within viewport bounds
            I don't know if this is working atm, this approcach of pulling each datapoint one at a time from the tooltips
            may be implemented later yet it will need javascript implementation to work fast enough."""
            
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
                    
                    time.sleep(0.1)
                    
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
        
        def extract_dates_from_tooltips(self, tooltip_data):
            """Extract dates and values from tooltip HTML data"""
            dates = []
            values = []
            
            for point in tooltip_data:
                try:
                    # Parse tooltip HTML
                    soup = BeautifulSoup(point['tooltip_data'], 'html.parser')
                    
                    # Extract date and value
                    date = soup.select_one('.tooltip-date').text
                    value = soup.select_one('.tooltip-value').text.replace(' Points', '')
                    try:
                        value = float(value)
                    except:
                        pass
                    
                    dates.append(date)
                    values.append(value)
                    
                except Exception as e:
                    print(f"Error parsing tooltip data: {str(e)}")
                    continue
            
            if dates and values:
                self.start_end = {
                    'start_date': dates[0],
                    'end_date': dates[-1],
                    'start_value': values[0], 
                    'end_value': values[-1]
                }
                return self.start_end
        
            return None

        def get_tooltip_text(self, tooltip_selector: str = '.highcharts-tooltip'):
            # Locate the tooltip element and extract the text
            tooltip_elements = self.driver.find_elements(By.CSS_SELECTOR, tooltip_selector)
            if tooltip_elements:
                for tooltip_element in tooltip_elements:
                    tooltip_text = tooltip_element.get_attribute("outerHTML")
                    print(tooltip_text)
                return tooltip_text
            else:
                return None
        
        def bail_out(self):
            self.driver.quit()
            return None
    
################# Selenium class below ##########################################

class generic_webdriver(object):
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

class TE_Scraper(object):
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
        self.start_end = None
    
    def load_page(self, url, wait_time=5):
        """Load page and wait for it to be ready"""
        self.series_name = url.split("/")[-1].replace("-", " ")
        try:
            self.driver.get(url)
            time.sleep(wait_time)  # Basic wait for page load
            return True
        except Exception as e:
            print(f"Error loading page: {str(e)}")
            return False
    
    def click_button(self, selector, selector_type=By.CSS_SELECTOR):
        """Click button and wait for response"""
        try:
            # Wait for element to be clickable
            button = self.wait.until(
                EC.element_to_be_clickable((selector_type, selector))
            )
            # Scroll element into view
            #self.driver.execute_script("arguments[0].scrollIntoView(true);", button)
            time.sleep(1)  # Brief pause after scroll
            button.click()
            return True
        except TimeoutException:
            print(f"Button not found or not clickable: {selector}")
            return False
        except Exception as e:
            print(f"Error clicking button: {str(e)}")
            return False
    
    def get_element(self, selector: str = ".highcharts-series path", selector_type=By.CSS_SELECTOR):
        """Find element by selector"""
        try:
            element = self.wait.until(
                EC.presence_of_element_located((selector_type, selector))
            )
            self.current_element = element
            return element
        except TimeoutException:
            print(f"Element not found: {selector}")
            return None
        except Exception as e:
            print(f"Error finding element: {str(e)}")
            return None
        
    def series_from_element(self, element: str = None, invert_the_series: bool = False):
        """Extract series data from element text"""
        if element is None:
            element = self.current_element
        
        datastrlist = element.get_attribute("d").split(" ")
        ser = pd.Series(datastrlist)
        ser_num = pd.to_numeric(ser, errors='coerce').dropna()

        exvals = ser_num[::2]; yvals = ser_num[1::2]
        exvals = exvals.sort_values().to_list()
        yvals = yvals.to_list()
        series = pd.Series(yvals, index = exvals, name = "Extracted Series")

        if invert_the_series:
            series = invert_series(series, max_val = self.y_axis.index.max())
        self.series = series

        self.pix0 = self.series.iloc[0]; self.pix1 = self.series.iloc[-1]
        return series
    
    def get_datamax_min(self):
        """Get the max and min values for the series using y-axis values..."""
        
        print("axisY0 = ", self.y_axis.iloc[0], "axisY1 =", self.y_axis.iloc[-1])
        px_range = self.y_axis.index[-1] - self.y_axis.index[0]
        labrange = self.y_axis.iloc[-1] - self.y_axis.iloc[0]
        self.unit_per_pix = labrange/px_range
        print("unit_per_pix: ", self.unit_per_pix)
        self.datamax = round(self.y_axis.iloc[-1] - (self.y_axis.index[-1] - self.series.max())*self.unit_per_pix, 3)
        self.datamin = round(self.y_axis.iloc[0] + (self.series.min()-self.y_axis.index[0])*self.unit_per_pix, 3)
        print("datamax: ", self.datamax, "datamin: ", self.datamin)
        return self.datamax, self.datamin
    
    def scale_series(self, right_way_up: bool = True):
        self.unscaled_series = self.series; scaled = None

        if hasattr(self, "datamax") and hasattr(self, "datamin"):
            if right_way_up:
                scaled = normalize_series(self.series, self.datamin, self.datamax)
            else:
                scaled = self.norm_inv_norm(min = self.datamin, max = self.datamax)
        else:
            print("datamax and datamin not found, run get_datamax_min() first.")

        ### Alternative method to scale series using y-axis values
        self.start_end["start_value"]
        self.px_per_unit_alt

        if scaled is not None:
            self.series = scaled
        else:
            print("Error scaling series.")
        return scaled

    def norm_inv_norm(self, series: pd.Series = None, min: float = 0, max: float = 100):
        """Normalize series to between 0 & 1 then invert series, tehn norm to between min and max."""
        if series is None:
            series = self.series

        # First normalize series to between 0 and 1
        norm_series = normalize_series(series, 0, 1)
        # Invert the series
        inv_series = 1 - norm_series
        # Normalize the series to the desired range
        fin_series = normalize_series(inv_series, min, max)

        self.series = fin_series
        return fin_series
    
    def get_xlims_from_tooltips(self):
        """ Use the get_tooltip class to get the start and end dates of the time series using the tooltip box displayed on the chart."""
        self.tooltip_scraper = get_tooltip(driver=self.driver, chart_x=335.5, chart_y=677.0)
        self.start_end = self.tooltip_scraper.retry_dates()

    def make_x_index(self):
        """Make the DateTime Index for the series using the start and end dates scraped from the tooltips. 
        """  ## May need to determine the frequency of data using a few more tooltip grabs. Do this later. 

        if hasattr(self, "start_end") and self.start_end is not None:
            pass
        else:
            self.get_xlims_from_tooltips()
        
        print("Start and end values scraped from tooltips: ", self.start_end)
        self.px_per_unit_alt = abs(float(self.start_end["start_value"]) - float(self.start_end["end_value"])) / abs(self.pix0-self.pix1)
        print("Start value - end value", self.px_per_unit_alt)

        print("Creating date index for self.series, using start and end dates from tooltips stored in self.start_end.")
        try:
            start_date = self.start_end["start_date"]; end_date = self.start_end["end_date"]
            dtIndex = self.dtIndex(start_date=start_date, end_date=end_date, ser_name=self.series_name)
            print("Date index created successfully. Take a look at the final series: \n\n", dtIndex)
            return dtIndex.index
        
        except Exception as e:
            print(f"Error creating date index: {str(e)}")
       

    def get_y_axis(self):
        """Get y-axis values from chart to make a y-axis index with tick labels and positions (pixel positions)."""

        ##Get positions of y-axis gridlines
        y_heights = []
        self.full_chart = self.get_element(selector = "#chart").get_attribute("outerHTML")
        self.chart_soup = BeautifulSoup(self.full_chart, 'html.parser')
        ygrid = self.chart_soup.select('g.highcharts-grid.highcharts-yaxis-grid')
        gridlines = ygrid[1].findAll('path')
        for line in gridlines:
            y_heights.append(float(line.get('d').split(' ')[-1]))
        y_heights = sorted(y_heights)

        ##Get y-axis labels
        soup2 = BeautifulSoup(self.full_chart, 'html.parser')
        yax = soup2.select('g.highcharts-axis-labels.highcharts-yaxis-labels')
        textels = yax[1].find_all('text')
        yaxlabs = [float(text.get_text()) if text.get_text().isdigit() else text.get_text() for text in textels]
        if any(isinstance(i, str) for i in yaxlabs):
            yaxlabs = [float(''.join(filter(str.isdigit, i.replace(",", "")))) if isinstance(i, str) else i for i in yaxlabs]
        pixheights = [float(height) for height in y_heights]
        pixheights.sort()

        ##Get px per unit for y-axis
        pxPerUnit = [abs((yaxlabs[i+1]- yaxlabs[i])/(pixheights[i+1]- pixheights[i])) for i in range(len(pixheights)-1)]
        average = sum(pxPerUnit)/len(pxPerUnit)
        print("Average px per unit for y-axis: ", average)

        yaxis = pd.Series(yaxlabs, index = pixheights, name = "ytick_label").round(1)
        yaxis.index.rename("pixheight", inplace = True)
        self.y_axis = yaxis
        return yaxis
    
    def dtIndex(self, start_date: str, end_date: str, ser_name: str = "Time-series"):
        """

        Create a date index for your series in self.series. Will first make an index to cover the full length of your series 
        and then resample to month start freq to match the format on Trading Economics.
        
        **Parameters:**
        - start_date (str) YYYY-MM-DD: The start date of your series
        - end_date (str) YYYY-MM-DD: The end date of your series
        - ser_name (str): The name TO GIVE the series
        """

        dtIndex = pd.date_range(start = start_date, end=end_date, periods=len(self.series))
        new_ser = pd.Series(self.series.to_list(), index = dtIndex, name = ser_name)
        new_ser = new_ser.resample("MS").first()  ## Use First to match the MS freq.
        self.series = new_ser
        return new_ser

    def extract_axis_limits(self):
        """Extract axis limits from the chart"""
        try:
            # Get the page source and parse it with BeautifulSoup
            html = self.get_element(selector = "#chart").get_attribute("outerHTML")
            soup = BeautifulSoup(html, 'html.parser')
            
            # Extract x-axis labels
            x_axis_labels = soup.select('.highcharts-axis-labels.highcharts-xaxis-labels span')
            x_values = [float(label.get_text()) for label in x_axis_labels]
            x_min = min(x_values)
            x_max = max(x_values)
            
            # Extract y-axis labels
            y_axis_labels = soup.select('.highcharts-axis-labels.highcharts-yaxis-labels span')
            y_values = [float(label.get_text()) for label in y_axis_labels]
            y_min = min(y_values)
            y_max = max(y_values)
            
            print('X-axis min:', x_min)
            print('X-axis max:', x_max)
            print('Y-axis min:', y_min)
            print('Y-axis max:', y_max)
            
            return x_min, x_max, y_min, y_max
        except Exception as e:
            print(f"Error extracting axis limits: {str(e)}")
            return None
    
    def plot_series(self, add_horizontal_lines: bool = False):
        fig = self.series.plot()

        if add_horizontal_lines:
        # Add horizontal lines and labels
            for i in range(len(self.y_axis)):
                fig.add_shape(
                    type='line',
                    x0=self.series.index.min(),
                    y0=self.y_axis.index[i],
                    x1=self.series.index.max(),
                    y1=self.y_axis.index[i],
                    line=dict(color='Red', dash='dash')
                )
                fig.add_annotation(
                    x=self.series.index.max(),  # Position the label at the end of the line
                    y=self.y_axis.index[i],
                    text=str(self.y_axis.iloc[i]),
                    showarrow=False,
                    xanchor='left',
                    yanchor='middle'
                )

            # Update layout to place legend at the bottom
        fig.update_layout(
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.2,  # Adjust this value to move the legend further down
                xanchor="center",
                x=0.5
            ))

        # Show the figure
        fig.show()

    def get_page_source(self):
        """Get current page source after interactions"""
        return self.driver.page_source
    
    def close(self):
        """Clean up resources"""
        if self.driver:
            self.driver.quit()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


############ Convenience function to run the full scraper ##########################################

def scrape_chart(url: str, driver: webdriver = None, headless: bool = True, browser: str = 'firefox') -> TE_Scraper:
    """ This convenience function will scrape a chart from Trading Economics and return a TE_Scraper object with the series data.

    ** Parameters: **

    - url (str): The URL of the chart to scrape.
    - headless (bool): Whether to run the browser in headless mode.
    - browser (str): The browser to use, either 'chrome' or 'firefox'.
    """
    loaded_page = False; clicked_button = False; yaxis = None; series = None; x_index = None; scaled_series = None; datamax = None; datamin = None

    sel = TE_Scraper(driver = driver, browser = browser, headless = headless)
    if sel.load_page(url):
        print("Page at ", url, ", loaded successfully.")
        loaded_page = True
    else:
        print("Error loading page at: ", url)
        return None

    if sel.click_button("a.hawk-chartOptions-datePicker-cnt-btn:nth-child(5)"):  ## This is the "MAX" button on the Trading Economics chart to set the chart to max length.
        print("Clicked the MAX button successfully.")
        clicked_button = True
    else:
        print("Error clicking the MAX button.")
        return None
    
    time.sleep(2)
    try:
        yaxis = sel.get_y_axis()
        print("Successfully scraped y-axis values from the chart:", " \n", yaxis)  
    except Exception as e:
        print(f"Error scraping y-axis: {str(e)}")
    
    try:
        sel.get_element()
        series = sel.series_from_element(invert_the_series=True)
        print("Successfully scraped raw pixel co-ordinate seruies from the path element in chart:", " \n", series)
        time.sleep(2)
    except Exception as e:
        print(f"Error scraping y-axis: {str(e)}")

    try:
        x_index = sel.make_x_index()
        time.sleep(1)
    except Exception as e:
        print(f"Error creating date index: {str(e)}")

    try:
        datamax, datamin = sel.get_datamax_min()   
        scaled_series = sel.scale_series(right_way_up=True)   
    except Exception as e:
        print(f"Error scaling series: {str(e)}")
    
    if loaded_page and clicked_button and yaxis is not None and series is not None and x_index is not None and scaled_series is not None and datamax is not None and datamin is not None:
        print("Successfully scraped time-series from chart at: ", url, " \n", sel.series)
        return sel
    else:
        print("Error scraping chart at: ", url) 
        return None
        

class search_TE(object):
    # Define browser type with allowed values
    BrowserType = Literal["chrome", "firefox"]
    
    def __init__(self, driver: webdriver = None, 
                 browser: BrowserType = "firefox", 
                 search_term: str = "US ISM Services PMI",
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

        self.search_term = search_term
        self.home_page()

    def home_page(self):
        # Load page
        try:
            print("Loading home page...")
            self.driver.get("https://tradingeconomics.com/")
        except Exception as e:
            print(f"Error occurred: {str(e)}")

    def search_trading_economics(self, search_term: str = None):

        self.current_page = self.driver.current_url
        if self.current_page != "https://tradingeconomics.com/":
            self.home_page()
            time.sleep(2)
 
        if search_term is None:
            search_term = self.search_term
        else:
            self.search_term = search_term
        
        try:
        # Wait for search box - using the ID from the HTML
            search_box = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "thisIstheSearchBoxIdTag")))
   
            
            # Click search box
            print("Clicking search box...")
            search_box.click()
            
            # Enter search term
            print(f"Entering search term: {search_term}")
            search_box.send_keys(search_term)
            time.sleep(1)  # Small delay to let suggestions appear
            
            # Press Enter
            print("Submitting search...")
            search_box.send_keys(Keys.RETURN)
            
            # Wait a moment to see results
            time.sleep(3)

            self.results = self.extract_search_results(self.driver.page_source)
            self.results_table()
        
        except Exception as e:
            print(f"Error occurred: {str(e)}")
            return None
        
    def extract_search_results(self, html_content):
        """Extract URLs from search results page"""
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Find all list items in search results
        results = soup.find_all('li', class_='list-group-item')
        
        urls = []
        for result in results:
            # Find the main link in each result item
            link = result.find('a', href=True)
            if link and link['href'].startswith('/'):
                full_url = f"https://tradingeconomics.com{link['href']}"
                urls.append(full_url)
        
        return urls
    
    def results_table(self):
        if hasattr(self, "results"):
            metrics = []
            countries = []
            for result in self.results:
                metrics.append(result.split("/")[-1].replace("-", " "))
                countries.append(result.split("/")[-2].replace("-", " "))
            df = pd.DataFrame({'country': countries, 'metric': metrics, "url": self.results})
            df.index.rename('result', inplace=True)
            self.result_table = df
        else:
            print("No search results found.")
            return None
        
    def get_data(self, result_num: int = 0):
        print("Attempting to scrape data for result ", result_num, ", ", self.result_table.loc[result_num, "country"], self.result_table.loc[result_num, "metric"] )
        if hasattr(self, "result_table"):
            url = self.result_table.loc[result_num, "url"]
            print(f"Scraping data from: {url}")
            self.scraped_data = scrape_chart(url, driver = self.driver, headless=self.headless, browser=self.browser)
            return self.scraped_data
        else:
            print("No search results found.")
            return None
  
if __name__ == "__main__":

    sickie = get_tooltip()
    sickie.bail_out()
