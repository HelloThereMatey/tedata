from typing import Union
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.common.exceptions import WebDriverException
import time
import pandas as pd
import numpy as np
import os 
import re 
import warnings
import timeit
import plotly.graph_objects as go

from . import logger, scraper

import logging
# Get the logger from the parent package
logger = logging.getLogger('tedata.utils')

##### Get the directory where this file is housed ########################
wd = os.path.dirname(__file__)
fdel= os.path.sep

def n_years_later(date: str = "1950-01-01", n_years: int = 5):
    """Get date string n years later"""
    return (pd.to_datetime(date) + pd.DateOffset(years=n_years)).strftime("%Y-%m-%d")

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
    
def get_date_frequency(date_series: pd.Series):
    """Get the frequency of a date series, for weekly returns day-specific frequency (e.g. W-SUN)"""
    if date_series.is_monotonic_increasing or date_series.is_monotonic_decreasing:
        diff = date_series.diff().dropna().mean()
        freq = pd.infer_freq(date_series)
        
        if freq is None:
            freq = map_frequency(diff)
        # If weekly frequency, determine the day
        if freq == 'W':
            day_map = {0: 'MON', 1: 'TUE', 2: 'WED', 3: 'THU', 
                        4: 'FRI', 5: 'SAT', 6: 'SUN'}
            weekday = date_series.iloc[0].dayofweek
            return f'W-{day_map[weekday]}'
        else:
            return freq
    else:
        return None
    
# BeautifulSoup approach
def check_element_exists_bs4(soup, selector):
    try:
        element = soup.select_one(selector)
        return element.text if element else None
    except:
        return None
    
def convert_metric_prefix(value_str: str) -> tuple[float, str]:
    """Convert string with metric prefix to float, and return the remaining text.
    
    Examples:
        '2.27K Thousand units' -> (2270.0, 'Thousand units')
        '10 K units' -> (10000.0, 'units')
        '1.3M' -> (1300000.0, '')
        '5B Points' -> (5000000000.0, 'Points')
    
    Args:
        value_str (str): String containing number and optional metric prefix
        
    Returns:
        tuple: (converted_numeric_value: float, remaining_text: str)
    """
    if value_str == "NaN":
        return np.nan, ""
        
    # Dictionary of metric prefixes and their multipliers
    metric_prefixes = {
        'K': 1000,
        'M': 1000000,
        'B': 1000000000,
        'G': 1000000000,
        'T': 1000000000000
    }
    
    try:
        # Clean and standardize input
        value_str = value_str.strip()
        orig_value_str = value_str  # Save original string for determining remainder
        value_str_upper = value_str.upper()
        
        # First try to match pattern like "2.27K" or "10K"
        match = re.match(r'^(-?\d*\.?\d+)\s*([KMGBT])?', value_str_upper)
        if not match:
            return float(value_str), ""  # No prefix case
            
        # Extract the numeric part and prefix
        number = float(match.group(1))
        prefix = match.group(2)
        
        # Calculate the length of the matched part including prefix
        matched_length = match.end()
        
        # Apply multiplier if prefix found
        if prefix and prefix in metric_prefixes:
            number *= metric_prefixes[prefix]
        
        # Extract remaining text (excluding the matched part)
        remaining = orig_value_str[matched_length:].strip()
            
        return number, remaining
        
    except Exception as e:
        logger.debug(f"Error converting value '{value_str}': {str(e)}")
        try:
            return float(value_str), ""
        except:
            return np.nan, value_str
    
def extract_and_convert_value(value_str: str) -> tuple[float, str]:
    """
    Extract numeric value with metric prefix from a string, convert it to a float,
    and return both the converted value and remaining non-numeric text. This is the complex version that will 
    
    Complex cases handled:
    - '1 M $' -> (1000000.0, '$')
    - '246 k Thousand' -> (246000.0, '')
    - '10 M million' -> (10000000.0, '')
    - '2.3 k %' -> (2300.0, '%')
    - '100 000.25 G' -> (100000250000000.0, '')
    - '0.673 x10^-6' -> (0.000000673, '')
    - '1.56 hundred Thousand' -> (156000.0, '')
    
    Args:
        value_str (str): String containing number and optional metric prefix
        
    Returns:
        tuple: (converted_numeric_value: float, remaining_text: str)
    """
    if value_str is None:
        return np.nan, ""
        
    if value_str == "NaN":
        return np.nan, ""
    
    if not isinstance(value_str, str):
        try:
            return float(value_str), ""
        except:
            return np.nan, str(value_str)
    
    # Dictionary of metric prefixes and their multipliers
    metric_prefixes = {
        'K': 1000,
        'M': 1000000,
        'B': 1000000000,
        'G': 1000000000,
        'T': 1000000000000
    }
    
    # # Word forms with their multipliers
    # word_multipliers = {
    #     'HUNDRED': 100,
    #     'THOUSAND': 1000,
    #     'MILLION': 1000000,
    #     'BILLION': 1000000000,
    #     'TRILLION': 1000000000000
    # }
    
    try:
        # Clean input string
        value_str = value_str.strip()
        
        # Handle scientific notation like "0.673 x10^-6"
        sci_notation_match = re.search(r'(\d+\.?\d*)\s*x\s*10\^(-?\d+)', value_str, re.IGNORECASE)
        if sci_notation_match:
            base = float(sci_notation_match.group(1))
            exponent = int(sci_notation_match.group(2))
            numeric_value = base * (10 ** exponent)
            # Remove the matched part from the string
            start, end = sci_notation_match.span()
            remaining = value_str[:start].strip() + " " + value_str[end:].strip()
            return numeric_value, remaining.strip()
            
        # First find any number in the string - this could be with commas or spaces
        # like "100 000.25" or "1,234.56"
        number_pattern = r'(-?[\d\s,.]+\d*)'
        number_match = re.search(number_pattern, value_str)
        
        if not number_match:
            return np.nan, value_str
            
        # Extract and clean the number
        number_str = number_match.group(1)
        # Remove spaces and replace commas with dots in number
        number_str = number_str.replace(' ', '').replace(',', '.')
        # Handle cases with multiple dots
        if number_str.count('.') > 1:
            # Keep only the last dot
            parts = number_str.split('.')
            number_str = ''.join(parts[:-1]) + '.' + parts[-1]
            
        numeric_value = float(number_str)
        
        # Split remaining text into words
        start, end = number_match.span()
        remaining = value_str[:start].strip() + " " + value_str[end:].strip()
        remaining = " ".join(remaining.split())  # Normalize spaces
        
        # Process with word boundaries respected
        # This ensures we only match whole words
        multiplier_applied = False
        final_remaining = []
        
        # Pattern to find standalone metric prefix letters
        # This ensures the letter has whitespace or boundary on both sides
        # Using re.findall to get all matches with positions
        tokens = re.split(r'(\s+)', remaining)
        filtered_tokens = []

        i = 0
        while i < len(tokens):
            token = tokens[i]
            # Skip whitespace tokens
            if re.match(r'\s+', token):
                i += 1
                continue
                
            token_upper = token.upper()
            
            # Case 1: Single letter metric prefix
            if len(token) == 1 and token_upper in metric_prefixes and not multiplier_applied:
                numeric_value *= metric_prefixes[token_upper]
                multiplier_applied = True
                i += 1
                continue
                
            # # Case 2: Word multiplier (whole word match)
            # found_word_match = False
            # for word, mult in word_multipliers.items():
            #     if token_upper == word and not multiplier_applied:
            #         numeric_value *= mult
            #         multiplier_applied = True
            #         found_word_match = True
            #         break
            # if found_word_match:
            #     i += 1
            #     continue

            # Keep this token
            filtered_tokens.append(token)
            i += 1
            
        # Rejoin the filtered tokens
        final_remaining = ''.join(filtered_tokens)
            
        return numeric_value, final_remaining.strip()
        
    except Exception as e:
        logger.debug(f"Error extracting value from '{value_str}': {str(e)}")
        try:
            return float(value_str), ""
        except:
            return np.nan, value_str
    
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

def round_to_month_start(dates: pd.DatetimeIndex):
    """Round dates to nearest month start.
    
    Args:
        dates: DatetimeIndex of dates to round
        
    Returns:
        DatetimeIndex: Dates rounded to nearest month start
    """
    def _round_single_date(dt):
        if dt.day > 15:
            # Roll forward to next month start
            if dt.month == 12:
                return pd.Timestamp(f"{dt.year + 1}-01-01")
            else:
                return pd.Timestamp(f"{dt.year}-{dt.month + 1:02d}-01")
        else:
            # Roll back to current month start
            return pd.Timestamp(f"{dt.year}-{dt.month:02d}-01")

    rounded_dates = [_round_single_date(dt) for dt in dates]
    return pd.DatetimeIndex(rounded_dates)

def round_to_freq(dates: pd.DatetimeIndex, freq: str) -> pd.DatetimeIndex:
    """Round dates to nearest frequency start.
    
    Args:
        dates: DatetimeIndex to round
        freq: Frequency string (e.g. 'MS', 'QS', 'AS', 'W-SUN')
    
    Returns:
        DatetimeIndex: Dates rounded to nearest frequency start
    """
    # Map common frequencies to period frequencies
    freq_map = {
        'MS': 'M',  # Month Start -> Month
        'QS': 'Q',  # Quarter Start -> Quarter
        'AS': 'A',  # Year Start -> Year
        'W-SUN': 'W'  # Week Start (Sunday) -> Week
    }
    
    # Convert frequency if needed
    period_freq = freq[0] #Try just taking the first letter of the frequency string.
    #freq_map.get(freq, freq)
    
    def _round_single_date(dt):
        # Get current and next period starts
        current_period = pd.Timestamp(dt).normalize().to_period(period_freq).to_timestamp()
        next_period = (pd.Timestamp(dt).normalize().to_period(period_freq) + 1).to_timestamp()
        
        # Calculate distances
        dist_to_current = abs((dt - current_period).total_seconds())
        dist_to_next = abs((dt - next_period).total_seconds())
        
        # Return closest period start
        return next_period if dist_to_next < dist_to_current else current_period

    rounded_dates = [_round_single_date(dt) for dt in dates]
    return pd.DatetimeIndex(rounded_dates)

########### Classes ##############################################################################


class TooltipScraper(scraper.TE_Scraper):
    """ Extended version of TE_Scraper with additional functionality to scrape tooltip data from a chart element using Selenium.
    Can be initilized using a TE_Scraper object or a new URL. If using a new URL, a new webdriver will be created. If using an existing
    TE_Scraper object, the webdriver from that object will be used and all attributes will be copied over.
    This can get x, y data from the tooltip box displayed by a site such as Trading Economics when the cursor
    is moved over a chart. It can move the cursor to specific points on the chart and extract tooltip text.
    It extracts date and value data from the tooltip text.
    Initialize the scraper with a URL and chart coordinates

    **init Parameters:**
    - parent_instance (scraper.TE_Scraper): A parent scraper object to copy attributes from. This is the most efficient way to initialize.
    - **kwargs: Keyword arguments to pass to the parent class, these are TE_Scraper init key word arguments.
    Generally you would not supply keyword arguments if you are using a parent_instance for initilization. The kwargs apply to creation
    of a new TE_Scraper object. See TE_scraper class for details on initialization of a fresh instance.

    """
    
    def __init__(self, parent_instance=None, **kwargs):
        """ Initialize the TooltipScraper object"""
        if parent_instance:  # Copy attributes from parent instance
            self.__dict__.update(parent_instance.__dict__)
            self.observers.append(self)
        else:
            super().__init__(**kwargs)
    
    def move_cursor(self, x: int = 0, y: int = 0):
        self.actions.move_to_element_with_offset(self.full_chart, x, y).perform()
        #print(f"Moved cursor to ({x}, {y})")
        return None
                        
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
    
    def first_last_dates_js(self):
        """Get first and last data points using JavaScript execution instead of ActionChains.
        More reliable across different browser implementations and environments."""

        self.initialize_tooltip_simple()  # Initialize tooltip by moving mouse to center of chart.

        # Load JavaScript code from file
        js_file_path = os.path.join(os.path.dirname(__file__), 'firstLastDates.js')
        try:
            with open(js_file_path, 'r') as file:
                js_code = file.read()
            
            # Execute the JavaScript function and wait for the Promise to resolve
            result = self.driver.execute_async_script(js_code)
            #print("Raw result from JavaScript:", result)
            
            if result is None:
                logger.info("JavaScript execution returned None")
                return None
                
            if isinstance(result, dict) and "error" in result:
                if "logs" in result and result["logs"]:
                    logger.info(f"JavaScript error: {result['error']}")
                    for log in result.get('logs', []):
                        logger.info(f"JS Log: {log}")
                else:
                    logger.info(f"JavaScript error: {result['error']}")
                return None

            #Add debug logging
            if isinstance(result, dict) and "debug" in result and "logs" in result["debug"]:
                for log in result["debug"]["logs"]:
                    logger.debug(f"JS Log: {log}")
                
            # Process dates from raw strings to pandas timestamps
            if result.get('start_date'):
                try:
                    # Convert using ready_datestr to handle Q1, Q2, etc.
                    result['start_date'] = pd.to_datetime(ready_datestr(result['start_date']))
                    print(f"Start date: {result['start_date']}")
                except Exception as e:
                    logger.error(f"Error parsing start date '{result['start_date']}': {str(e)}")
                    # Keep the string value if parsing fails
            
            if result.get('end_date'):
                try:
                    # Convert using ready_datestr to handle Q1, Q2, etc.
                    result['end_date'] = pd.to_datetime(ready_datestr(result['end_date']))
                    print(f"End date: {result['end_date']}")
                except Exception as e:
                    logger.info(f"Error parsing end date '{result['end_date']}': {str(e)}")

            if result.get('start_value'):
                try:
                    # Convert using ready_datestr to handle Q1, Q2, etc.
                    valtup = extract_and_convert_value(result['start_value'])
                    result['start_value'] = valtup[0]
                    result['unit_str'] = valtup[1]
                except Exception as e:
                    logger.info(f"Error parsing end date '{result['end_date']}': {str(e)}")
            
            if result.get('end_value'):
                try:
                    valtup = extract_and_convert_value(result['end_value'])
                    result['end_value'] = valtup[0]
                    result['unit_str'] = valtup[1]
                except Exception as e:
                    logger.info(f"Error parsing end date '{result['end_value']}': {str(e)}")
                
            # Log successful result for debugging
            logger.debug(f"Successfully retrieved first/last dates: \n{result}")
            # Remove debug field to keep the result clean
            if isinstance(result, dict) and "debug" in result:
                del result["debug"]
                
            return result
        
        except Exception as e:
            logger.error(f"Error executing JavaScript for first/last dates: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def first_last_dates(self):
        """Scrape first and last data points for the data series on the chart at TE using viewport coordinates.

        **Returns:**
        - start_end: dict containing the start and end dates and values of the data series.

        """
        self.update_chart()
        self.get_chart_dims()

        # Calculate exact positions of left and right extremes
        left_x =  0 # Left edge x-coordinate relative to self.axes_rect["x"]
        right_x = self.axes_rect['width'] # Right edge x-coordinate
        y_pos =  self.axes_rect['height'] # Middle of chart
        # NOTE: USING THE MIDDLE OF THE CHART (in Y) WILL REQUIRE LINE CHART_TYPE.
        
        start_end = {}
        actions = ActionChains(self.driver)
        actions.move_to_element(self.plot_background)
        actions.reset_actions()
        
        # For each extreme (left and right)
        positions = {
            ("start_date", "start_value"): left_x,
            ("end_date", "end_value"): right_x
        }

        for (date_key, value_key), x_pos in positions.items():
            # Reset cursor by moving to plot background first

            actions.move_by_offset(x_pos, y_pos).perform()
            time.sleep(1.5)
            
            # Get tooltip
            date, value, unit_str = self.extract_date_value_tooltip()
            start_end[date_key] = date
            start_end[value_key] = value
            start_end["unit_str"] = unit_str
            actions.reset_actions()
        
        print("Determined start and end dates and values: ", start_end)
        
        return start_end

    def latest_points_js(self, num_points: int = 10, increment: int = None, wait_time: int = None, 
                        force_shortest_span: bool = True):
        """Get data points by moving cursor across chart within viewport bounds using JavaScript.
        Gets date and values from the tooltips that show up.
        
        Args:
            num_points (int): Number of unique data points to collect before stopping. Use "all" to collect all points
            increment (int, optional): Override the default increment calculation. Pixels to move per step
            wait_time (int, optional): Override the default wait time between moves (milliseconds)
            force_shortest_span (bool): Whether to force the chart to shortest timespan before scraping
        
        Returns:
            list: List of data points as dictionaries with 'date' and 'value' keys
        """

        if force_shortest_span:
            shortest_span = list(self.date_spans.keys())[0]
            if self.date_span != shortest_span: # Set the datespan to 1 year to look just at the latest data points
                self.set_date_span(shortest_span)
                time.sleep(0.5)
        spline_step = timeit.default_timer()
        self.set_chartType_js("Spline") #Force spline chart selection - very important. I still have no way to determine if the chart type has changed when it changes automatically.
        #Chart type must be spline or line for this to work. Sometimes the chart_type chnages automatically when datespan is altered.
        logger.info(f"Time taken to select chart type: {timeit.default_timer() - spline_step}")

        # First we'll try to get first & last points:
        # success = False
        # for attempt in range(3):
        #     self.start_end = self.first_last_dates_js()
        #     if (self.start_end is None or 
        #         not all(key in self.start_end for key in ["start_date", "end_date"]) or
        #         any(pd.isna(self.start_end[key]) for key in ["start_date", "end_date"]))\
        #         or any(self.start_end[key] is None for key in ["start_date", "end_date"]):
        #         print("Retrying start_end extraction...")
        #         time.sleep(0.25)
        #     else:
        #         logger.info("Start_end extracted successfully:", self.start_end)
        #         success = True
        #         break
        # if not success:
        #     logger.info("Failed to extract start & end points, this could adversely affect the rest of the tooltip scraping..")

        self.initialize_tooltip_simple() #Initialize the tooltip by moving the mouse to the center of the chart.
        try:
            # Load JavaScript code from file
            js_file_path = os.path.join(os.path.dirname(__file__), 'latest_points.js')
            with open(js_file_path, 'r') as file:
                js_code = file.read()
            
            # Build options object, only including provided values
            options = {'num_points': num_points}
            if increment is not None:
                options['increment_override'] = increment
            if wait_time is not None:
                options['wait_time_override'] = wait_time
            
            # Pass single options object to async script
            js_step = timeit.default_timer()
            result = self.driver.execute_async_script(js_code, options)
            logger.info(f"Time taken to execute JS code: {timeit.default_timer() - js_step}")

            if isinstance(result, dict):
                # for log in result.get('logs', []):
                #     logger.info(f"JS Console: {log}")
                    
                datapoints = result.get('dataPoints', [])
                
                # Process datapoints to handle NaN values
                for point in datapoints:
                    if point['value'] == "NaN":
                        point['value'] = np.nan
                            
                return datapoints
            else:
                logger.debug("Unexpected result format")
                return []
                
        except Exception as e:
            logger.info(f"Error in execution of the js_script to get : {str(e)}")
            return []
        
    def get_device_pixel_ratio(self):
        """Get device pixel ratio to scale movements"""
        return self.driver.execute_script('return window.devicePixelRatio;')
        
    def extract_date_value_tooltip(self):
        """Extract date and value from a single tooltip HTML"""
        # Extract date and value using Selenium
        valfound = False; datefound = False
        try: 
            date_element = self.driver.find_element(By.CSS_SELECTOR, '.tooltip-date').text.strip()
            datefound = True
            date = pd.to_datetime(ready_datestr(date_element))
        except:
            pass

        #Get value from tooltip
        try: 
            value_element = self.driver.find_element(By.CSS_SELECTOR, '.tooltip-value').text.replace(' Points', '').strip()
            valfound = True
            valtup = extract_and_convert_value(value_element)
            value = valtup[0]
        except:
            pass

        if datefound and valfound:
            return date, value, valtup[1]
        elif datefound:
            return date, np.nan, ""
        elif valfound:
            return "", value, valtup[1]
        else:
            return "", np.nan, ""

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
            #print("Tooltip not found")
            return None
          
    def show_position_marker(self, x: int, y: int, duration_ms: int = 5000):
        """Add visual marker at specified coordinates"""
        js_code = """
            // Create dot element
            const dot = document.createElement('div');
            dot.style.cssText = `
                position: absolute;
                left: ${arguments[0]}px;
                top: ${arguments[1]}px;
                width: 10px;
                height: 10px;
                background-color: red;
                border-radius: 50%;
                z-index: 9999;
                pointer-events: none;
            `;
            document.body.appendChild(dot);
            
            // Remove after duration
            setTimeout(() => dot.remove(), arguments[2]);
        """
        self.driver.execute_script(js_code, x, y, duration_ms)

    def mark_cursor_position(self, duration_ms: int = 5000):
        """Mark current cursor position with dot"""
        js_code = """
            let cursor_x = 0;
            let cursor_y = 0;
            
            document.addEventListener('mousemove', function(e) {
                cursor_x = e.pageX;
                cursor_y = e.pageY;
            });
            
            return [cursor_x, cursor_y];
        """
        coords = self.driver.execute_script(js_code)
        if coords and len(coords) == 2:
            self.show_position_marker(coords[0], coords[1], duration_ms)
            return coords
        return None

    def move_cursor_on_chart(self, x: int = 0, y: int = 0, printout: bool = False):
        """Move cursor to chart origin (0,0) point"""

        if not hasattr(self, 'axes_rect'):
            self.get_chart_dims()
        x_pos = self.axes_rect['x'] + x
        y_pos = self.axes_rect['y'] - y
        
        # Move to origin
        actions = ActionChains(self.driver)
        actions.move_by_offset(x_pos, y_pos).perform()
        actions.reset_actions()
        self.show_position_marker(x_pos, y_pos)
        if printout:
            print(f"Moved cursor to chart position ({x_pos}, {y_pos})")
            print(f"Moved cursor to chart position ({x_pos}, {y_pos})")
    
    def bail_out(self):
        self.driver.quit()
        return None
    
    def move_with_marker(self, x: int, y: int):
        """Move to position and show marker"""
        actions = ActionChains(self.driver)
        actions.move_by_offset(x, y).perform()
        actions.reset_actions()
        self.show_position_marker(x, y)

    def initialize_tooltip_simple(self):
        """Initialize tooltip by moving mouse to center of chart with a single browser event"""
        
        with open(os.path.join(os.path.dirname(__file__), 'init_tooltips.js'), 'r') as file:
            script = file.read()
        
        try:
            result = self.driver.execute_script(script)
            initial = result.get('initialState', {})
            final = result.get('finalState', {})
            
            if result.get('success'):
                logger.info("Successfully initialized tooltip with simple mouse event\n")
                logger.debug(f"Initial state: {initial}\nFinal state: {final}")
                return True
            else:
                initial = result.get('initialState', {})
                final = result.get('finalState', {})
                logger.info(
                    f"Failed to initialize tooltip with simple mouse event: {result.get('error')}\n"
                    f"Initial state: {initial}\n"
                    f"Final state: {final}\n"
                    f"Chart found: {result.get('hasChart')}"
                )
                return False
        except Exception as e:
            logger.error(f"Error during simple tooltip initialization: {str(e)}")
            return False

    ### Other utility functions for the TooltipScraper class ##########################################

def get_chart_datespans(scraper_object: Union[scraper.TE_Scraper, TooltipScraper], selector: str = "#dateSpansDiv"):
    """Get the date spans from the Trading Economics chart currently displayed in the scraper object. The scraper object can be a TE_Scraperfrom the scraper module
    or TooltipScraper object from the utils module.
    
    ** Parameters:**
    - scraper_object (TE_Scraper or TooltipScraper): The scraper object with the chart to scrape.
    - selector (str): The CSS selector to find the date spans element. Default is '#dateSpansDiv'.
    
    ** Returns:**
    - date_spans (dict): A dictionary with date span names as keys and CSS selectors for the button to select that span as values.
    """
    if not isinstance(scraper_object, TooltipScraper) or not isinstance(scraper_object, scraper.TE_Scraper):
        print("get_chart_datespans function: Invalid scraper object supplies as first arg, must be a scraper.TE_Scraper or utils.TooltipScraper object.")
        return None
    try:
        buts = scraper_object.page_soup.select_one(selector)
        datebut = buts[0] if isinstance(buts, list) else buts
        scraper_object.date_spans = {child.text: f"a.{child['class'][0] if isinstance(child['class'], list) else child['class']}:nth-child({i+1})" for i, child in enumerate(datebut.children)}
        return scraper_object.date_spans
    except Exception as e:
        print(f"get_chart_datespans function: Error finding date spans, error: {str(e)}")
        return None

def click_button(scraper_object: Union[scraper.TE_Scraper, TooltipScraper], 
                 selector: str = "#dateSpansDiv", 
                 selector_type=By.CSS_SELECTOR):
    
    """Click button and wait for response..."""

    try:
        # Wait for element to be clickable
        button =  WebDriverWait(scraper_object.driver, timeout=10).until(
            EC.element_to_be_clickable((selector_type, selector))
        )
        # Scroll element into view
        #self.driver.execute_script("arguments[0].scrollIntoView(true);", button)
        time.sleep(0.25)  # Brief pause after scroll
        button.click()
        #logger.info("Button clicked successfully, waiting 1s for response...")
        logger.info(f"Button clicked successfully: {selector} on object {scraper_object}")
        time.sleep(0.75)
        return True

    except Exception as e:
        logger.info(f"Error clicking button: {str(e)} on object {scraper_object}")
        return False
    
def show_position_marker(scraper_object: Union[scraper.TE_Scraper, TooltipScraper], 
                         x: int, y: int, duration_ms: int = 5000):
    """Add visual marker at specified coordinates"""

    if not isinstance(scraper_object, TooltipScraper) or not isinstance(scraper_object, scraper.TE_Scraper):
        print("get_chart_datespans function: Invalid scraper object supplies as first arg, must be a scraper.TE_Scraper or utils.TooltipScraper object.")
        return None
    
    js_code = """
        // Create dot element
        const dot = document.createElement('div');
        dot.style.cssText = `
            position: absolute;
            left: ${arguments[0]}px;
            top: ${arguments[1]}px;
            width: 10px;
            height: 10px;
            background-color: red;
            border-radius: 50%;
            z-index: 9999;
            pointer-events: none;
        `;
        document.body.appendChild(dot);
        
        // Remove after duration
        setTimeout(() => dot.remove(), arguments[2]);
    """
    scraper_object.driver.execute_script(js_code, x, y, duration_ms)

def plot_multi_series(series_list: list = None,
                    right_series_list: list = None,
                    metadata: dict = None,
                    right_metadata: dict = None,
                    annotation_text: str = None, 
                    ann_box_pos: tuple = (0, - 0.2),
                    colors: list = None,
                    right_colors: list = None,
                    show_fig: bool = True,
                    return_fig: bool = False):
    """
    Plots multiple series on a single chart using Plotly, with support for dual Y-axes.
    
    **Parameters**
    - series_list (list): List of series to plot on left Y-axis. Can be a list of pandas Series objects
      or a list of dicts with format [{"series": series1, "add_name": "string"}, ...].
    - right_series_list (list): List of series to plot on right Y-axis, same format as series_list.
    - metadata (dict): Dictionary with metadata for left axis series (keys like "country", "title", "units").
    - right_metadata (dict): Dictionary with metadata for right axis series, similar to metadata.
    - annotation_text (str): Text to display in annotation box at the bottom of chart.
    - colors (list): List of color names for left axis traces. Default cycles through standard colors.
    - right_colors (list): List of color names for right axis traces. Default uses a different palette.
    - ann_box_pos (tuple): Position of annotation box. Default is (0, -0.2) which is bottom left.
    - show_fig (bool): Whether to display the figure immediately.
    - return_fig (bool): Whether to return the plotly figure object.

    **Returns** 
    - fig: Plotly figure object (if return_fig=True)
    """
    # Create a new figure
    fig = go.Figure()
    
    # Default colors for left and right axes if none provided
    if colors is None:
        colors = ['blue', 'red', 'green', 'purple', 'orange', 'brown', 'pink', 'gray']
    if right_colors is None:
        right_colors = ['darkred', 'darkgreen', 'darkblue', 'darkorange', 'darkcyan', 'darkmagenta']
    
    # Add left axis series
    if series_list:
        not_dicts = False
        for i, series in enumerate(series_list):
            if isinstance(series, pd.Series):
                not_dicts = True
                series = {"series": series, "add_name": ""}
                
            try:
                ser = series["series"]
                logger.info(f"Adding left axis series {ser.name} to plot")
                if not_dicts:
                    name = ser.name
                else:
                    name = ser.name+" (method: "+series["add_name"]+")" if ser.name else f"Series {i+1}"
                color = colors[i % len(colors)]  # Cycle through colors 
                fig.add_trace(go.Scatter(
                    x=ser.index, 
                    y=ser.values,
                    name=name, 
                    line=dict(color=color), 
                    mode='lines'
                ))
            except Exception as e:
                print(f"Error adding left axis series to plot: {str(e)}")
                continue
    
    # Add right axis series
    if right_series_list:
        not_dicts = False
        for i, series in enumerate(right_series_list):
            if isinstance(series, pd.Series):
                not_dicts = True
                series = {"series": series, "add_name": ""}
                
            try:
                ser = series["series"]
                logger.info(f"Adding right axis series {ser.name} to plot")
                if not_dicts:
                    name = ser.name
                else:
                    name = ser.name+" (method: "+series["add_name"]+")" if ser.name else f"Right axis {i+1}"
                color = right_colors[i % len(right_colors)]  # Cycle through colors 
                fig.add_trace(go.Scatter(
                    x=ser.index, 
                    y=ser.values,
                    name=name, 
                    line=dict(color=color), 
                    mode='lines',
                    yaxis="y2"  # Use the secondary y-axis
                ))
            except Exception as e:
                print(f"Error adding right axis series to plot: {str(e)}")
                continue
    
    # Set title and Y-axis labels based on metadata
    title = "Time Series Plot"
    left_ylabel = "Value"
    right_ylabel = "Value (Right Axis)"
    
    if metadata is not None:
        title = str(metadata.get("country", "")).capitalize() + ": " + str(metadata.get("title", "")).capitalize()
        left_ylabel = str(metadata.get("units", "Value")).capitalize()
        
        # Create default annotation text from metadata
        frequency = metadata.get("frequency", "Unknown")
        if annotation_text is None:
            annotation_text = (
                f"Source: {metadata.get('source', 'Unknown')}<br>"
                f"Original Source: {metadata.get('original_source', 'Unknown')}<br>"
                f"Frequency: {frequency}<br>"
            )
    
    if right_metadata is not None:
        right_ylabel = str(right_metadata.get("units", "Value (Right Axis)")).capitalize()
        # Add to annotation text if it exists
        if annotation_text and right_metadata.get("units"):
            annotation_text += f"Right Axis: {right_metadata.get('units', 'Value')}<br>"
    
    # If no annotation text was created, set a default
    annotation_text = annotation_text or "Source: Trading Economics"
    
    # Add text annotation to bottom left
    fig.add_annotation(
        text=annotation_text, 
        xref="paper", 
        yref="paper",
        x=ann_box_pos[0], 
        y=ann_box_pos[1], 
        showarrow=False, 
        font=dict(size=10),
        align="left", 
        xanchor="left", 
        yanchor="bottom", 
        bgcolor="rgba(255, 255, 255, 0.8)",
        bordercolor="black", 
        borderwidth=1
    )
    
    # Update layout with dual y-axes
    fig.update_layout(
        title=title,
        xaxis=dict(title=""),
        yaxis=dict(
            title=left_ylabel),
        yaxis2=dict(
            title=right_ylabel,
            anchor="x",
            overlaying="y",
            side="right"
        ),
        legend=dict(
            title_text="",  # Remove legend title
            orientation="h", 
            yanchor="bottom",
            y=-0.2,  # Adjust this value to move the legend further down
            xanchor="center", 
            x=0.5)
    )
    
    if show_fig:
        fig.show()
    if return_fig:
        return fig