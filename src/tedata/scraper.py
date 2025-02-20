from typing import Literal
from collections import OrderedDict
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.keys import Keys
import time
import datetime
import pandas as pd
import os 

fdel = os.path.sep

# tedata related imports
from . import utils, logger
from .base import Generic_Webdriver, SharedWebDriverState

# Create module-specific logger
logger = logger.getChild('scraper')

## Standalone functions  ########################################
def find_element_header_match(soup: BeautifulSoup, selector: str, match_text: str):
    """Find .card-header element with text matching search_text"""
    elements = soup.select(selector)
    print("Elements found from selector, number of them: ", len(elements))
    for ele in elements:
        print("\n", str(ele), "\n")
        if str(ele.header.text).strip().lower() == match_text.lower():
            print("Match found: ", ele.header.text)
            return ele
    return None

### Main workhorse class for scraping data from Trading Economics website.
class TE_Scraper(Generic_Webdriver, SharedWebDriverState):
    """Class for scraping data from Trading Economics website. This is the main workhorse of the module.
    It is designed to scrape data from the Trading Economics website using Selenium and BeautifulSoup.
    It can load a page, click buttons, extract data from elements, and plot the extracted data. Uses multiple inheritance
    from the Generic_Webdriver and SharedWebDriverState classes. This enables creation of TooltipScraper child classes that have 
    synced atributes such as "chart_soup", "chart_type" & "date_span" & share the same webdriver object. This is useful for scraping.

    **Init Parameters:** 
    - **kwargs (dict): Keyword  arguments to pass to the Generic_Webdriver class. These are the same as the Generic_Webdriver class.
    These are:
        - driver (webdriver): A Selenium WebDriver object, can put in an active one or make a new one for a new URL.
        - use_existing_driver (bool): Whether to use an existing driver in the namespace. If True, the driver parameter is ignored. Default is False.
        - browser (str): The browser to use for scraping, either 'chrome' or 'firefox'.
        - headless (bool): Whether to run the browser in headless mode (show no window).
    """

    # Define browser type with allowed values
    BrowserType = Literal["chrome", "firefox"]  #Chrome still not working as of v0.2.4..
    def __init__(self, **kwargs):
        Generic_Webdriver.__init__(self, **kwargs)
        SharedWebDriverState.__init__(self)
        self.observers.append(self)  # Register self as observer
        self._shared_state = self  # Since we inherit SharedWebDriverState, we are our own shared state

    def load_page(self, url, wait_time=2):
        """Load page and wait for it to be ready"""

        self.last_url = url
        self.series_name = url.split("/")[-1].replace("-", " ")
        try:
            self.driver.get(url)
            #logger.debug(f"Page loaded successfully: {url}")
            logger.info(f"WebPage at {url} loaded successfully.")
            time.sleep(wait_time)  # Basic wait for page load
            self.full_page = self.get_page_source()
            self.page_soup = BeautifulSoup(self.full_page, 'html.parser')
            self.chart_soup = self.page_soup.select_one("#chart")  #Make a bs4 object from the #chart element of the page.
            self.full_chart = self.chart_soup.contents
            self.create_chart_types_dict() # Create the chart types dictionary for the chart.
            self.determine_date_span()  # Determine the date span from the chart.
            return True
        except Exception as e:
            print(f"Error loading page: {str(e)}")
            logger.debug(f"Error loading page: {str(e)}")
            return False
    
    def click_button(self, selector, selector_type=By.CSS_SELECTOR):
        """Click button using webdriver and wait for response.
        
        **Parameters:**
        - selector (str): The CSS selector for the button to click.
        - selector_type (By): The type of selector to use, By.CSS_SELECTOR by default."""

        try:
            # Wait for element to be clickable
            button = self.wait.until(
                EC.element_to_be_clickable((selector_type, selector))
            )
            # Scroll element into view
            time.sleep(0.25)  # Brief pause after scroll
            button.click()
            time.sleep(0.75)
            return True
        except TimeoutException:
            logger.info(f"Button not found or not clickable: {selector}")
            return False
        except Exception as e:
            logger.info(f"Error clicking button: {str(e)}")
            return False

    def find_max_button(self, selector: str = "#dateSpansDiv"):
        """Find the button on the chart that selects the maximum date range and return the CSS selector for it.
        The button is usually labelled 'MAX' and is used to select the maximum date range for the chart. The selector for the button is
        usually '#dateSpansDiv' but can be changed if the button is not found. The method will return the CSS selector for the button.
        This will also create an atrribute 'date_spans' which is a dictionary containing the text of the date span buttons and their CSS selectors."""

        try:
            buts = self.page_soup.select_one(selector)
            datebut = buts[0] if isinstance(buts, list) else buts
            self.date_spans = {child.text: f"a.{child['class'][0] if isinstance(child['class'], list) else child['class']}:nth-child({i+1})" for i, child in enumerate(datebut.children)}

            if "MAX" in self.date_spans.keys():
                max_selector = self.date_spans["MAX"]
            else:
                raise ValueError("MAX button not found.")
            logger.debug(f"MAX button found for chart at URL: {self.last_url}, selector: {max_selector}")
            
            return max_selector
        except Exception as e:
            print(f"Error finding date spans buttons: {str(e)}")
            logger.debug(f"Error finding date spans buttons: {str(e)}")
            return None
    
    def click_max_button(self):
        """Click the button that selects the maximum date range on the chart. This is usually the 'MAX' button and is used to select the maximum date range for the chart.
        The method will find the button and click it. It will also wait for the chart to update after clicking the button."""
        max_selector = self.find_max_button()
        if self.click_button(max_selector):
            time.sleep(1)
            logger.info("MAX button clicked successfully.")
            self.date_span = "MAX"
            self.update_chart()
        else:
            logger.debug("Error clicking MAX button.")
            return False
        
    def determine_date_span(self, update_chart: bool = True):
        """Determine the selected date span from the Trading Economics chart currently displayed in webdriver."""

        if update_chart: 
            self.update_chart()
        ## Populate the date spans dictionary
        buts = self.chart_soup.select("#dateSpansDiv")
        datebut = buts[0] if isinstance(buts, list) else buts
        self.date_spans = OrderedDict()
        for i, child in enumerate(datebut.children):
            selector = f"a.{child['class'][0] if isinstance(child['class'], list) else child['class']}:nth-child({i+1})"
            self.date_spans[child.text] = selector

        ## Find the selected date span
        if len(buts) == 1:
            result = buts[0].children
        elif len(buts) > 1:
            print("Multiple date spans found")
            return buts
        else:
            print("No date spans found")
            return None

        for r in result:
            #print("Date span element: ", r)
            if "selected"in r["class"]:
                date_span = {r.text: r}
                return date_span
            else:
                return None

    def update_chart(self):
        """Update the chart attributes after loading a new page or clicking a button. This will check the page source and update the 
        beautiful soup objects such as chart_soup, from which most other methods derive their functionality. It will also update the full_chart attribute
        which is the full HTML of the chart element on the page. This method should be run after changing something on the webpage via driver such
        as clicking a button to change the date span or chart type."""

        try:
            # Since we inherit from SharedWebDriverState, we can directly set the page_source property
            self.page_source = self.driver.page_source
            return True

        except Exception as e:
            logger.error(f"Failed to update chart: {e}")
            return False

    def set_date_span(self, date_span: str):
        """Set the date span on the Trading Economics chart. This is done by clicking the date span button on the chart. The date span is a button on the chart
        that allows you to change the date range of the chart. This method will click the button for the date span specified in the date_span parameter.
        The date_span parameter should be a string that matches one of the date span buttons on the chart. The method will also update the date_span attribute
        of the class to reflect the new date span."""
        if not hasattr(self, "date_spans"):
            self.determine_date_span()
        if date_span in self.date_spans.keys():
            if self.click_button(self.date_spans[date_span]):
                self.date_span = date_span
                logger.info(f"Date span set to: {date_span}")
                self.update_chart()
                return True
            else:
                logger.info(f"Error setting date span: {date_span}, check that the date span button is clickable.")
                return False
        else:
            logger.info(f"Error setting date span: {date_span}, check that the supplied date span matches one of the keys in the self.date_spans attribute (dict).")
            return False
        
    def set_max_date_span_viaCalendar(self):
        """ Looks like Trading Economics have gone ahead and made the "MAX" button on charts a subscriber only feature. No problem, we can still set the max date range
        by using the calendar widget on the chart. This method will click the calendar button and then enter an arbitrary date far in the past as start date and the 
        current date as the end date."""

        self.custom_date_span(start_date="1850-01-01", end_date=datetime.date.today().strftime("%Y-%m-%d"))

    def update_date_span(self, update_chart: bool = False):
        """Update the date span after clicking a button. This will check the page source and update the date span attribute.
        This method can be used t check that the curret date span is correct after clicking a button to change it. 
        It will update the date_span attribute. It is not necessary after running set_date_span though as that method already updates the date span attribute.

        **Parameters:**
        - update_chart (bool): Whether to update the chart before determining the date span. Default is False.
        """

        if update_chart:
            self.update_chart()
        self.date_span_dict = self.determine_date_span()
        self.date_span = list(self.date_span_dict.keys())[0]
    
    def create_chart_types_dict(self):
        """Create a dictionary of chart types and their CSS selectors. This is used to select the chart type on the Trading Economics chart.
        The dictionary is stored in the chart_types attribute of the class. The keys are the names of the chart types and the values are the CSS selectors
        for the chart type buttons on the chart."""

        hart_types = self.chart_soup.select_one("#chart > div > div > div.hawk-header > div > div.pickChartTypes > div > div")
        self.chart_types = {child["title"]: "."+child["class"][0]+" ."+ child.button["class"][0] for child in hart_types.children}
        self.expected_types = {chart_type: self.chart_types[chart_type].split(" ")[0].replace(".", '') for chart_type in self.chart_types.keys()}
        logger.info(f"Chart types dictionary created successfully: {self.chart_types.keys()}")

    def select_line_chart(self, update_chart: bool = False):
        """Select the line chart type on the Trading Economics chart. This is done by clicking the chart type button and then selecting the line chart type."""

        if update_chart:
            self.update_chart()
        if not hasattr(self, "chart_types"):
            self.create_chart_types_dict()

        if self.click_button("#chart > div > div > div.hawk-header > div > div.pickChartTypes > div > button"):
            if self.click_button(self.chart_types["Line"]):
                self.chart_type = "lineChart"
                logger.info("Line chart type selected.")
                self.update_chart()
                return True
        else:
            print("Error selecting line chart type.")
            logger.debug("Error selecting line chart type.")
            return None
    
    def select_chart_type(self, chart_type: str):
        """Select a chart type on the Trading Economics chart. This is done by clicking the chart type button and then selecting the specified chart type.
        The chart type should be a string that matches one of the chart types in the chart_types dictionary. The method will click the chart type button
        and then select the specified chart type. It will also update the chart_type attribute of the class to reflect the new chart type.

        **Parameters:**
        - chart_type (str): The chart type to select on the chart. This must be one of the keys of the chart_types dictionary attribute of the class.
        List the options by printing self.chart_types.keys()
        """
        if not hasattr(self, "chart_types"):
            self.create_chart_types_dict()

        if chart_type in self.chart_types.keys():
            if self.click_button("#chart > div > div > div.hawk-header > div > div.pickChartTypes > div > button"):
                self.click_button(self.chart_types[chart_type])
                self.chart_type = self.expected_types[chart_type]
                logger.info(f"Chart type set to: {chart_type}")
                self.update_chart()
                return True
            else:
                logger.debug(f"Error selecting chart type: {chart_type}")
                return False
        else:
            logger.debug(f"Chart type not found: {chart_type}")
            return False

    ## Determine chart type from the chart displayed in the webdriver. This is not working yet,
    # the buttons are not easi;y distinguishable, leave for now. chart_type will have to bve remembered and
    # only set via the select_chart_type or select_line chart methods.  
    # def determine_chart_type(self, update_chart: bool = True):
    #     """ Determine the chart type from the Trading Economics chart currently displayed in webdriver.
    #     This is done by checking the class of the selected chart type button in the chart. The chart type is determined by the class of the SVG element
    #     in the chart. This method will return the chart type as a string. 

    #     **Parameters:**
    #     - update_chart (bool): Whether to update the chart before determining the chart type. Default is False.
    #     """
    #     if update_chart:
    #         self.update_chart()
    #     if not hasattr(self, "chart_types") or not hasattr(self, "expected_types"):
    #         self.create_chart_types_dict()

    #     print("Chart types: ", self.chart_types)
    #     print("determine_chart_type method: Expected chart types: ", self.expected_types)
    #     res = self.chart_soup.select(".dkLabels-label-btn.selectedChartType")
        
    #     self.chart_type_svgs = {
    #         'Column': 'M4,9.2h2.057143v9.8L4,19v-9.8ZM9.04,5h1.92v14h-1.92v-14Zm5.04,8h1.92v6h-1.92v-6Z',
    #         'Spline': 'M1 15v-15h-1v16h16v-1h-15z',
    #         'Areaspline': 'M1 15v-15h-1v16h16v-1h-15z',
    #         'Stepline': <rect height="0.8" rx="0" ry="0" stroke-width="0" transform="translate(2.2081 12.419091)" width="10.1919"></rect>,
    #         'Line': 'M3.5 18.49L9.5 12.48L13.5 16.48L22 6.92L20.59 5.51L13.5 13.48L9.5 9.48L2 16.99L3.5 18.49Z',
    #         'Area': 'M1 15v-15h-1v16h16v-1h-15z'}
    #     return res
    #     # print("Selected chart type buttons: ", "\n", res,"\n")
    #     # for r in res:  # This is a list of the selected chart type buttons.
    #     #     print("Parent class: ", r.parent, "\n", r, "\n", "Child class: ", r.children)
    #     #     if any(expected_type in r.parent["class"] for expected_type in self.expected_types.values()):
    #     #         self.chart_type = r.parent["class"][0]
    #     #         logger.info(f"Chart type determined: {self.chart_type}")
    #     #         return self.chart_type
    #     logger.debug("Error determining chart tyoe: Chart type not found.")
    #     return None
    
    def get_element(self, selector: str = ".highcharts-series path", selector_type=By.CSS_SELECTOR):
        """Find element by selector. The data trace displayed on a Trading Economics chart is a PATH element in the SVG chart.
        This is selected using the CSS selector ".highcharts-series path" by default. The element is stored in the 'current_element' attribute.
        It can be used to select other elements on the chart as well and assign that to current element attribute.
        
        **Parameters:**
        - selector (str): The CSS selector for the element to find.
        - selector_type (By): The type of selector to use, By.CSS_SELECTOR by default.

        **Returns:**
        - element: The found element or None if not found.
        """
        try:
            element = self.wait.until(
                EC.presence_of_element_located((selector_type, selector))
            )
            self.current_element = element
            logger.info(f"Element found and assigned to current_element attribute: {selector}")
            return element
        except TimeoutException:
            print(f"Element not found: {selector}")
            logger.debug(f"Element not found: {selector}")
            return None
        except Exception as e:
            print(f"Error finding element: {str(e)}")
            logger.debug(f"Error finding element: {str(e)}")
            return None
        
    def series_from_chart_soup(self, selector: str = ".highcharts-tracker-line", 
                               invert_the_series: bool = True, 
                               set_max_datespan: bool = False,
                               local_run: bool = False,
                               use_chart_type: Literal["Line", "Spline"] = "Spline"):  
          
        """Extract series data from element text. This extracts the plotted series from the svg chart by taking the PATH 
        element of the data tarace on the chart. Series values are pixel co-ordinates on the chart.

        **Parameters:**
        - invert_the_series (bool): Whether to invert the series values.
        - return_series (bool): whether or not to return the series at end. Series is assigned to self.series always.
        - set_max_datespan (bool): Whether to set the date span to MAX before extracting the series data. Default is False.
        - local_run (bool): Whether the method is being run to get the full date_span series or just extacting part of the series
        to then aggregate together the full series. Default is False.
        - use_chart_type (str): The chart type to use for the extraction of the series data. Default is "Spline". This is used to set the chart type before extracting the series data.
        CUATION: This method may fail with certain types of charts. It is best to use Spline unless you have a reason to use another type.

        **Returns:**

        - series (pd.Series): The extracted series data that is the raw pixel co-ordinate values of the data trace on the svg chart.
        """

        self.update_chart() # Update chart..

        if self.chart_type != self.expected_types[use_chart_type]:
            self.select_chart_type(use_chart_type) ## Use a certain chart type for the extraction of the series data. May fail with certain types of charts.

        if set_max_datespan and self.date_span != "MAX":
            self.set_date_span("MAX")
        logger.info(f"Series path extraction method: Extracting series data from chart soup.") 
        logger.info(f"Date span: {self.date_span}. Chart type: {self.chart_type}, URL: {self.last_url}.")
    
        datastrlist = self.chart_soup.select(selector)
        
        if len(datastrlist) > 1:
            print("Multiple series found in the chart. Got to figure out which one to use... work to do here... This will not work yet, please report error.")
            raise ValueError("Multiple series found in the chart. Got to figure out which one to use... work to do here...")
        else:
            raw_series = self.chart_soup.select_one(".highcharts-graph")["d"].split(" ")
    
        ser = pd.Series(raw_series)
        ser_num = pd.to_numeric(ser, errors='coerce').dropna()

        exvals = ser_num[::2]; yvals = ser_num[1::2]
        exvals = exvals.sort_values().to_list()
        yvals = yvals.to_list()
        series = pd.Series(yvals, index = exvals, name = "Extracted Series")

        if local_run:
            y_axis = self.get_y_axis()
        else:
            y_axis = self.y_axis

        if invert_the_series:
            series = utils.invert_series(series, max_val = y_axis.index.max())
        
        if not local_run:
            self.trace_path_series_raw = series.copy()
         # Keep the raw pixel co-ordinate valued series extracted from the svg path element.
        logger.debug(f"Raw data series extracted successfully: {series.head(2)}")
        self.series_extracted_from = use_chart_type  #Add this attribute so that the apply_x_index method knows which chart_type the series came from.
        self.series = series
        return series
    
    def custom_date_span(self, start_date: str = "1900-01-01", end_date: str = datetime.date.today().strftime("%Y-%m-%d")) -> bool:
        """Set the date range on the active chart in the webdriver window. 
        This is done by entering the start and end dates into the date range input boxes
        
        Args:
            start_date (str): Start date in format YYYY-MM-DD
            end_date (str): End date in format YYYY-MM-DD
        """

        if self.click_button("#dateInputsToggle"):
            time.sleep(0.1)
            try:
                # Find elements
                start_input = self.wait.until(EC.presence_of_element_located((By.ID, "d1")))
                end_input = self.wait.until(EC.presence_of_element_located((By.ID, "d2")))
                
                # Clear existing text
                start_input.clear()
                end_input.clear()
                
                # Enter new dates
                start_input.send_keys(start_date)
                end_input.send_keys(end_date)
                
                # Press Enter to confirm
                end_input.send_keys(Keys.RETURN)
                self.date_span = {"Custom": {"start_date": start_date, "end_date": end_date}}
                return True
                
            except Exception as e:
                logger.info(f"Failed to enter dates: {e}")
                return False
        else:
            logger.info("Failed to open date range inputs")
            return False
    
    def get_datamax_min(self):
        """Get the max and min data values for the series using y-axis values... This is deprecated and not used in the current version of the code."""
        
        logger.debug(f"get_datamax_min method, axisY0 = {self.y_axis.iloc[0]}, axisY1 = {self.y_axis.iloc[-1]}")
        px_range = self.y_axis.index[-1] - self.y_axis.index[0]
        labrange = self.y_axis.iloc[-1] - self.y_axis.iloc[0]
        self.unit_per_pix_alt2 = labrange/px_range
        print("unit_per_pix: ", self.unit_per_pix)
        logger.debug(f"unit_per_pix: {self.unit_per_pix}, alt2: {self.unit_per_pix_alt2}")
        self.datamax = round(self.y_axis.iloc[-1] - (self.y_axis.index[-1] - self.series.max())*self.unit_per_pix, 3)
        self.datamin = round(self.y_axis.iloc[0] + (self.series.min()-self.y_axis.index[0])*self.unit_per_pix, 3)
        print("datamax: ", self.datamax, "datamin: ", self.datamin)
        logger.debug(f"datamax: {self.datamax}, datamin: {self.datamin}")
        return self.datamax, self.datamin
    
    def scale_series(self, right_way_up: bool = True):
        """Scale the series using the first and last values from the series pulled from the tooltip box. Uses the y axis limits and the max and min of the y axis
        to determine the scaling factor to convert pixel co-ordinates to data values. The scaling factor is stored in the self.axlims_upp attribute."""

        if not right_way_up:
            max_val = self.y_axis.index.max()  # This should be the top pixel of the chart.
            self.series = utils.invert_series(self.series, max_val = max_val)

        if hasattr(self, "start_end"):
            y0 = self.start_end["start_value"]; y1 = self.start_end["end_value"]
            pix0 = self.series.iloc[0]; pix1 = self.series.iloc[-1]
            
            self.unit_per_px_alt = abs(y1 - y0) / abs(pix1 - pix0)  # Calculated from the start and end datapoints.
            
            if not hasattr(self, "axis_limits"):
                self.axis_limits = self.extract_axis_limits()
            ## Turns out that this formulation below is the best way to calculate the scaling factor for the chart.
            self.axlims_upp = (self.y_axis.iloc[-1] - self.y_axis.iloc[0]) / (self.axis_limits["y_max"] - self.axis_limits["y_min"])

            # if the start and end points are at similar values this will be problematic though. 
            logger.debug("Scale series method: "
                        f"Start value, end value: {y0}, {y1}, pix0, pix1: {pix0}, {pix1}, "
                         f"data units per chart pixel from start & end points: {self.unit_per_px_alt}, "
                         f"unit_per_pix calculated from the y axis ticks: {self.unit_per_pix}, "
                         f"inverse of that: {1/self.unit_per_pix}, "
                         f"unit_per_pix from axis limits and self.y_axis (probably best way): {self.axlims_upp}")

            self.unscaled_series = self.series.copy()
            ##Does the Y axis cross zero? Where is the zero point??
            x_intercept = utils.find_zero_crossing(self.series)

            if x_intercept:
                logger.debug(f"Y axis Series does cross zero at:  {x_intercept}")
                pix0 = x_intercept

            for i in range(len(self.series)):
                self.series.iloc[i] = (self.series.iloc[i] - pix0)*self.axlims_upp + y0
    
            self.series = self.series
        else:
            print("start_end not found, run get_datamax_min() first.")
            logger.debug("start_end not found, run get_datamax_min() first.")
            return

        return self.series
    
    def get_xlims_from_tooltips(self):
        """ Use the TooltipScraper class to get the start and end dates and some other points of the time series using the tooltip box displayed on the chart.
        Takes the latest num_points points from the chart and uses them to determine the frequency of the time series. The latest data is used
        in case the earlier data is of lower frequency which can sometimes occurr.
        
        **Parameters:**
        
        - force_rerun (bool): Whether to force a rerun of the method to get the start and end dates and frequency of the time series again. The method
        will not run again by default if done a second time and start_end and frequency attributes are already set. If the first run resulted in erroneous
        assignation of these attributes, set this to True to rerun the method. However, something may need to be changed if it is not working..."""

        print("get_xlims_from_tooltips method: date_span: ", self.date_span, ", chart_type:", self.chart_type)

        if self.date_span != "MAX":
            self.set_date_span("MAX")  ##Set date_span to MAX for start and end date pull...
        self.select_chart_type("Spline") #Force spline chart selection - very important. I still have no way to determine if the chart type has changed when it changes automatically.
        #Chart type must be spline or line for this to work. Sometimes the chart_type chnages automatically when datespan is altered.

        if not hasattr(self, "tooltip_scraper"):
            self.tooltip_scraper = utils.TooltipScraper(parent_instance = self) # Create a tooltip scraper child object
        
        self.start_end = self.tooltip_scraper.first_last_dates()
        #print("Start and end dates scraped from tooltips: ", self.start_end)

    def make_x_index(self, 
                     force_rerun_xlims: bool = False,
                     force_rerun_freqdet: bool = False):
        """Make the DateTime Index for the series using the start and end dates scraped from the tooltips. 
        This uses Selenium and also scrapes the some of the latest datapoints from the tooltips on the chart in order to determine
        the frequency of the time series. It will take a bit of time to run.

        **Parameters:**
        - force_rerun_xlims (bool): Whether to force a rerun of the method to get the start and end dates and frequency of the time series again. The method
        will not run again by default if done a second time and start_end and frequency attributes are already set. 
        - force_rerun_freqdet (bool): Whether to force a rerun of the method to get the frequency of the time series again. The method
        will not run again by default if done a second time and frequency attribute is already set. 
        """
        ## Update chart...
        self.update_chart()

        if not hasattr(self, "tooltip_scraper"):  # If the tooltip scraper object is not already created, create it.
            self.tooltip_scraper = utils.TooltipScraper(parent_instance = self) # Create a tooltip scraper child object

        print("Using selenium and tooltip scraping to construct the date time index for the time-series, this'll take a bit...")
        ## Get the latest 10 or so points from the chart, date and value from tooltips, in order to determine the frequency of the time series.
        if force_rerun_freqdet or not hasattr(self, "latest_points"):
            #datapoints = self.tooltip_scraper.get_latest_points(num_points = 5)  # Python version, slow
            datapoints = self.tooltip_scraper.latest_points_js(num_points=10)  # js version, faster
            self.latest_points = datapoints
            latest_dates = [datapoint["date"] for datapoint in datapoints]
            print("Latest dates: ", latest_dates)

            ## Get the frequency of the time series
            self.date_series = pd.Series(latest_dates[::-1]).astype("datetime64[ns]")
            self.frequency = utils.get_date_frequency(self.date_series)
        print("Frequency of time-series: ", self.frequency)

        if force_rerun_xlims or not hasattr(self, "start_end"):
            self.get_xlims_from_tooltips()
        # Get the first and last datapoints from the chart at MAX datespan

        if self.start_end is not None:
            logger.info(f"Start and end values scraped from tooltips: \n{self.start_end}")
        else:
            print("Error: Start and end values not found...pulling out....")
            logger.debug(f"Error: Start and end values not found...pulling out....")
            return None

        start_date = self.start_end["start_date"]; end_date = self.start_end["end_date"]
        dtIndex = self.dtIndex(start_date=start_date, end_date=end_date, ser_name=self.series_name)
        if dtIndex is not None:
            logger.info(f"DateTimeIndex created successfully for the time-series.")
            self.x_index = dtIndex
            return dtIndex  
        else:
            logger.info(f"Error creating DateTimeIndex for the time-series.")
            return None

    def get_y_axis(self, update_chart: bool = False, set_global_y_axis: bool = False):
        """Get y-axis values from chart to make a y-axis series with tick labels and positions (pixel positions).
        Also gets the limits of both axis in pixel co-ordinates. A series containing the y-axis values and their pixel positions (as index) is assigned
        to the "y_axis" attribute. The "axis_limits" attribute is made too & is  dictionary containing the pixel co-ordinates of the max and min for both x and y axis.

        **Parameters:**
        - update_chart (bool): Whether to update the chart before scraping the y-axis values. Default is False.
        - set_global_y_axis (bool): Whether to set the y-axis series as a global attribute of the class. Default is False.
        """

        ##Get positions of y-axis gridlines
        y_heights = []
        if update_chart:
            self.update_chart()
        if set_global_y_axis and self.date_span != "MAX":
            self.set_date_span("MAX")

        ## First get the pixel values of the max and min for both x and y axis.
        self.axis_limits = self.extract_axis_limits()

        ygrid = self.chart_soup.select('g.highcharts-grid.highcharts-yaxis-grid')
        gridlines = ygrid[1].findAll('path')
        for line in gridlines:
            y_heights.append(float(line.get('d').split(' ')[-1]))
        y_heights = sorted(y_heights)

        ##Get y-axis labels
        yax = self.chart_soup.select('g.highcharts-axis-labels.highcharts-yaxis-labels')
        textels = yax[1].find_all('text')

        # Replace metrc prefixes:
        yaxlabs = [utils.convert_metric_prefix(text.get_text()) if text.get_text().replace(',','').replace('.','').replace('-','').replace(' ','').isalnum() else text.get_text() for text in textels]
        logger.debug(f"y-axis labels: {yaxlabs}")

        # convert to float...
        if any(isinstance(i, str) for i in yaxlabs):
            yaxlabs = [float(''.join(filter(str.isdigit, i.replace(",", "")))) if isinstance(i, str) else i for i in yaxlabs]
        pixheights = [float(height) for height in y_heights]
        pixheights.sort()

        ##Get px per unit for y-axis
        pxPerUnit = [abs((yaxlabs[i+1]- yaxlabs[i])/(pixheights[i+1]- pixheights[i])) for i in range(len(pixheights)-1)]
        average = sum(pxPerUnit)/len(pxPerUnit)
        if set_global_y_axis:
            self.unit_per_pix = average
        logger.debug(f"Average px per unit for y-axis: {average}")  #Calculate the scaling for the chart so we can convert pixel co-ordinates to data values.

        yaxis = pd.Series(yaxlabs, index = pixheights, name = "ytick_label")
        yaxis.index.rename("pixheight", inplace = True)
        try:
            yaxis = yaxis.astype(float)
        except:
            pass

        if yaxis is not None:
            logger.debug(f"Y-axis values scraped successfully.")
            logger.info(f"Y-axis values scraped successfully.")
        
        if set_global_y_axis:
            self.y_axis = yaxis

        return yaxis
     
    def init_tooltipScraper(self):
        """Initialise the TooltipScraper object for the class. This is used to scrape the tooltip box on the chart to get the start and end dates of the time series.
        The tooltip scraper is a child object of the class and is used
        to scrape the tooltip box on the chart to get the start and end dates of the time series. The tooltip scraper is a child object of the class an shares some synced 
        attributes with the parent class. """

        if not hasattr(self, "tooltip_scraper"):
            self.tooltip_scraper = utils.TooltipScraper(parent_instance = self)
            logger.info(f"TooltipScraper object initialised successfully.")
        else:    
            logger.info(f"TooltipScraper object already initialised.")

    def dtIndex(self, start_date: str, end_date: str, ser_name: str = "Time-series") -> pd.DatetimeIndex:
        """

        Create a date index for your series in self.series. Will first make an index to cover the full length of your series 
        and then resample to month start freq to match the format on Trading Economics.
        
        **Parameters:**
        - start_date (str) YYYY-MM-DD: The start date of your series
        - end_date (str) YYYY-MM-DD: The end date of your series
        - ser_name (str): The name TO GIVE the series
        """

        if hasattr(self, "series") and not hasattr(self, "frequency"):
            logger.info("Series found but frequency not known. Creating a datetime x-index for series with frequency determined by length of series.\
                        Returning dtIndex only.")
            dtIndex = pd.date_range(start = start_date, end=end_date, periods=len(self.series), inclusive="both")
            return dtIndex
        elif hasattr(self, "series") and hasattr(self, "frequency"):
            dtIndex = pd.date_range(start = start_date, end=end_date, freq = self.frequency)
            new_ser = pd.Series(self.series.to_list(), index = dtIndex, name = ser_name)
            self.trace_path_series = new_ser.copy()
            new_ser = new_ser.resample(self.frequency).first()
            self.series = new_ser
            logger.info(f"Series is already scraped, frequency and start, end dates are known. DatetimeIndex created\
                        for series, set as index and series resampled at the frequency: {self.frequency}. series attribute updated.")
            return dtIndex
        elif not hasattr(self, "series") and hasattr(self, "frequency"):
            logger.debug("No series found, using frequency and start and end dates to create a datetime x-index.")
            dtIndex = pd.date_range(start = start_date, end=end_date, freq = self.frequency)
            return dtIndex
        else:
            logger.info("No series found, frequenc unknown get the series or frequency first. Returning None")
            return None 
        
    def apply_x_index(self, x_index: pd.DatetimeIndex = None, use_rounded_tempIndex: bool = False, redo_series: bool = False):
        """Apply a datetime index to the series. This will set the datetime index as the index of the series and resample the series to the frequency
        of the datetime index. The series attribute of the class will be updated with the new series.

        **Parameters:**
        - x_index (pd.DatetimeIndex): The datetime index to apply to the series. If None, the x_index attribute of the class will be used.
        """
        if x_index is None and not hasattr(self, "x_index"):
            print("No datetime x-index found. Run make_x_index() first.")
            return None
        elif x_index is None:
            x_index = self.x_index
        else:
            pass

        if redo_series:
            self.series = self.trace_path_series_raw.copy()

        if hasattr(self, "series"):
            if self.series_extracted_from == "Line":
                if len(x_index) == len(self.series):
                    new_ser = pd.Series(self.series.to_list(), index = self.x_index, name = self.series_name)
                elif len(x_index) > len(self.series):
                    print("Length of x_index is greater than length of series. This is unfortunate, dunno what to do here...")
                    return None
                else: # use_rounded_tempIndex:
                    temp_index = pd.date_range(start = x_index[0], end = x_index[-1], periods=len(self.series))
                    temp_index = utils.round_to_freq(temp_index, self.frequency)
                    new_ser = pd.Series(self.series.to_list(), index = temp_index, name = self.series_name)
                    new_ser = new_ser.resample(self.frequency).first()
            elif self.series_extracted_from == "Spline":
                temp_index = pd.date_range(start = x_index[0], end = x_index[-1], periods=len(self.series))
                #print("temp_index: ", temp_index, "len series: ", len(self.series), "len x_index: ", len(x_index))
                new_ser = pd.Series(self.series.to_list(), index = temp_index, name = self.series_name)
                self.trace_path_series = new_ser.copy()
                new_ser = new_ser.resample(self.frequency).first()
            else:
                logger.info("Series not extracted from Line or Spline chart. Cannot apply datetime index, go back and run the series_from_chart_soup method.")
                return None
            
            self.series = new_ser  # Update the series attribute with the new series.
            logger.info(f"DateTimeIndex applied to series, series attribute updated.")
        else:
            logger.info("No series found, get the series first.")
            return None

    def extract_axis_limits(self):
        """Extract axis limits from the chart in terms of pixel co-ordinates."""
        logger.debug(f"Extracting axis limits from the chart...")
        try:
            # Extract axis elements
            yax = self.chart_soup.select_one("g.highcharts-axis.highcharts-yaxis path.highcharts-axis-line")
            xax = self.chart_soup.select_one("g.highcharts-axis.highcharts-xaxis path.highcharts-axis-line")
            
            ylims = yax["d"].replace("M", "").replace("L", "").strip().split(" ")
            ylims = [float(num) for num in ylims if len(num) > 0][1::2]
            logger.debug(f"yax: {ylims}")

            xlims = xax["d"].replace("M", "").replace("L", "").strip().split(" ")
            xlims = [float(num) for num in xlims if len(num) > 0][0::2]
            logger.debug(f"xax: {xlims}")
            
            axis_limits = {
                'x_min': xlims[0],
                'x_max': xlims[1],
                'y_min': ylims[0],
                'y_max': ylims[1]
            }
            
            return axis_limits
        except Exception as e:
            print(f"Error extracting axis limits: {str(e)}")
            logger.debug(f"Error extracting axis limits: {str(e)}")
            return None
    
    def plot_series(self, series: pd.Series = None, 
                    annotation_text: str = None, 
                    dpi: int = 300, 
                    ann_box_pos: tuple = (0, - 0.2)):
        """
        Plots the time series data using pandas with plotly as the backend. Plotly is set as the pandas backend in __init__.py for tedata.
        If you want to use matplotlib or other plotting library don't use this method, plot the series attribute data directly. If using jupyter
        you can set 

        **Parameters**
        - series (pd.Series): The series to plot. Default is None. If None, the series attribute of the class will be plotted.
        - annotation_text (str): Text to display in the annotation box at the bottom of the chart. Default is None. If None, the default annotation text
        will be created from the metadata.
        - dpi (int): The resolution of the plot in dots per inch. Default is 300.
        - ann_box_pos (tuple): The position of the annotation box on the chart. Default is (0, -0.23) which is bottom left.

        **Returns** None
        """
        
        if series is None:
            series = self.series

        fig = series.plot()  # Plot the series using pandas, plotly needs to be set as the pandas plotting backend.

         # Existing title and label logic
        if hasattr(self, "series_metadata"):
            title = str(self.series_metadata["country"]).capitalize() + ": " + str(self.series_metadata["title"]).capitalize()
            ylabel = str(self.series_metadata["units"]).capitalize()
            
            # Create default annotation text from metadata
            if annotation_text is None:
                annotation_text = (
                    f"Source: {self.series_metadata['source']}<br>"
                    f"Original Source: {self.series_metadata['original_source']}<br>"
                    f"Frequency: {self.series_metadata['frequency']}"
                )
        else:
            title = "Time Series Plot"
            ylabel = "Value"
            annotation_text = annotation_text or "Source: Trading Economics"

        # Add text annotation to bottom left
        fig.add_annotation(
            text=annotation_text,
            xref="paper", yref="paper",
            x=ann_box_pos[0], y=ann_box_pos[1],
            showarrow=False, font=dict(size=10),
            align="left",  xanchor="left",
            yanchor="bottom", bgcolor="rgba(255, 255, 255, 0.8)",
            bordercolor="black", borderwidth=1)

        # Label x and y axis
        fig.update_layout(
            legend=dict(
            title_text="",  # Remove legend title
            orientation="h",
            yanchor="bottom",
            y=-0.2,  # Adjust this value to move the legend further down
            xanchor="center",
            x=0.5
            ),
            yaxis_title=ylabel,
            xaxis_title="",
            title = title)

        # Show the figure
        fig.show()
        self.plot = fig

    def save_plot(self, filename: str = "plot", save_path: str = os.getcwd(), dpi: int = 300, format: str = "png"):
        """Save the plot to a file. The plot must be created using the plot_series method. This method will save the plot as a PNG image file.

        **Parameters**
        - filename (str): The name of the file to save the plot to. Default is 'plot.png'.
        - save_path (str): The directory to save the plot to. Default is the current working directory.
        - dpi (int): The resolution of the plot in dots per inch. Default is 300.
        - format (str): The format to save the plot in. Default is 'png'. Other options are: "html", "bmp", "jpeg", "jpg".
        Use "html" to save as an interactive plotly plot.

        :Returns: None
        """

        if hasattr(self, "plot"):
            if format == "html":
                self.plot.write_html(f"{save_path}{fdel}{filename}.html")
                logger.info(f"Plot saved as {save_path}{fdel}{filename}.html")
            else:
                self.plot.write_image(f"{save_path}{fdel}{filename}.{format}", format=format, scale=dpi/100, width = 1400, height = 500)
                logger.info(f"Plot saved as {filename}")
        else:
            print("Error: Plot not found. Run plot_series() method to create a plot.")
            logger.debug("Error: Plot not found. Run plot_series() method to create a plot.")

    def scrape_metadata(self):
        """Scrape metadata from the page. This method scrapes metadata from the page and stores it in the 'metadata' attribute. The metadata
        includes the title, indicator, country, length, frequency, source, , original source, id, start date, end date, min value, and max value of the series.
        It also scrapes a description of the series if available and stores it in the 'description' attribute.
        """

        self.metadata = {}
        logger.debug(f"Scraping metadata for the series from the page...")

        try:
            self.metadata["units"] = self.chart_soup.select_one('#singleIndChartUnit2').text
        except Exception as e:
            print("Units label not found: ", {str(e)})
            self.metadata["units"] = "a.u"
        
        try:
            self.metadata["original_source"] = self.chart_soup.select_one('#singleIndChartUnit').text
        except Exception as e:
            print("original_source label not found: ", {str(e)})
            self.metadata["original_source"] = "unknown"

        if hasattr(self, "series"):
            if hasattr(self, "page_soup"):
                heads = self.page_soup.select("#ctl00_Head1")
                self.metadata["title"] = heads[0].title.text.strip()
            else:
                self.metadata["title"] = self.last_url.split("/")[-1].replace("-", " ")  # Use URL if can't find the title
            self.metadata["indicator"] = self.last_url.split("/")[-1].replace("-", " ")  
            self.metadata["country"] = self.last_url.split("/")[-2].replace("-", " ") 
            self.metadata["length"] = len(self.series)
            self.metadata["frequency"] = self.frequency  
            self.metadata["source"] = "Trading Economics" 
            self.metadata["id"] = "/".join(self.last_url.split("/")[-2:])
            self.metadata["start_date"] = self.series.index[0].strftime("%Y-%m-%d")
            self.metadata["end_date"] = self.series.index[-1].strftime("%Y-%m-%d")
            self.metadata["min_value"] = float(self.series.min())
            self.metadata["max_value"] = float(self.series.max())
            logger.info(f"\nSeries metadata: \n {self.metadata}")

        try:
            desc_card = self.page_soup.select_one("#item_definition")
            header_text = desc_card.select_one('.card-header').text.strip()
            if header_text.lower() == self.metadata["title"].lower():
                self.metadata["description"] = desc_card.select_one('.card-body').text.strip()
            else:
                print("Description card title does not match series title.")
                self.metadata["description"] = "Description not found."
        except Exception as e:
            print("Description card not found: ", {str(e)})

        self.series_metadata = pd.Series(self.metadata)
        if self.metadata is not None:
            logger.debug(f"Metadata scraped successfully: {self.metadata}")

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

############################################################################################################
############ Convenience function to run the full scraper from scraper module ##########################################

def scrape_chart(url: str = "https://tradingeconomics.com/united-states/business-confidence", 
                 id: str = None,
                 country: str = "united-states",
                 scraper: TE_Scraper = None,
                 driver: webdriver = None, 
                 use_existing_driver: bool = False,
                 headless: bool = True, 
                 browser: str = 'firefox') -> TE_Scraper:
    
    """ This convenience function will scrape a chart from Trading Economics and return a TE_Scraper object with the series data in
    the 'series' attribute. Metadata is also retreived and stored in the 'series_metadata' & 'metadata' attributes.
    
    *There are multiple ways to use this function:*

    - Supply URL of the chart to scrape OR supply country + id of the chart to scrape. country and id are just the latter parts of the 
    full chart URL. e.g for URL: 'https://tradingeconomics.com/united-states/business-confidence', we could instead use country='united-states' 
    and id='business-confidence'. You can supply only id and default country is 'united-states'.
    - You can leave scraper and driver as None and the function will create a new TE_Scraper object for that URL and use it to scrape the data.
    You can however save time by passing either a scraper object or a driver object to the function. Best to pass a driver object
    for fastest results.
    
    **Parameters**

    - url (str): The URL of the chart to scrape.
    - id (str): The id of the chart to scrape. This is the latter part of the URL after the country name.
    - country (str): The country of the chart to scrape. Default is 'united-states'.
    - scraper (TE_Scraper): A TE_Scraper object to use for scraping the data. If this is passed, the function will not create a new one.
    - driver (webdriver): A Selenium WebDriver object to use for scraping the data. If this is passed, the function will not create a new one. If 
    scraper and driver are both passed, the webdriver of the scraper object will be used rather than the supplied webdriver.
    - headless (bool): Whether to run the browser in headless mode (display no window).
    - browser (str): The browser to use, either 'chrome' or 'firefox'. Default is 'firefox'. Only firefox is supported at the moment (v0.2.4).

    **Returns**
    - TE_Scraper object with the scraped data or None if an error occurs.
    """

    if scraper is not None:       #Initialize TE_Scraper object..
        sel = scraper
        if driver is None:
            driver = scraper.driver
        else:
            scraper.driver = driver
    else:
        sel = TE_Scraper(driver = driver, browser = browser, headless = headless, use_existing_driver=use_existing_driver)

    if id is not None:   #Use country and id to create the URL if URL not supplied.
        url = f"https://tradingeconomics.com/{country}/{id}"

    logger.info(f"scrape_chart function: Scraping chart at: {url}, time: {datetime.datetime.now()}")
    if sel.load_page(url):  # Load the page...
        pass
    else:
        print("Error loading page at: ", url)
        logger.debug(f"Error loading page at: {url}")
        return None

    try: #Create the x_index for the series. This is the most complicated bit.
        sel.make_x_index(force_rerun_xlims = True, force_rerun_freqdet = True)  
    except Exception as e:
        print("Error with the x-axis scraping & frequency deterination using Selenium and tooltips:", str(e))
        logger.debug(f"Error with the x-axis scraping & frequency deterination using Selenium and tooltips: {str(e)}")
        return None

    try:  #Scrape the y-axis values from the chart.
        sel.get_y_axis(set_global_y_axis=True)
        #print("Successfully scraped y-axis values from the chart:", " \n", yaxis) 
        logger.debug(f"Successfully scraped y-axis values from the chart.") 
    except Exception as e:
        print(f"Error scraping y-axis: {str(e)}")
        logger.debug(f"Error scraping y-axis: {str(e)}")
        return None
    
    try:
        sel.series_from_chart_soup(set_max_datespan=True)  #Get the series data from path element on the svg chart.
        logger.debug("Successfully scraped full series path element.")
    except Exception as e:
        print("Error scraping full series: ", str(e))
        logger.debug(f"Error scraping full series: {str(e)}")
        return None

    try: 
        sel.apply_x_index()  ## Apply the x_index to the series, this will resample the data to the frequency of the x_index.
        logger.debug("Successfully applied x_index scaling to series.")
    except Exception as e:
        print(f"Error applying x-axis scaling: {str(e)}")
        logger.debug(f"Error applying x-axis scaling: {str(e)}")
        return None

    try:  
        scaled_series = sel.scale_series()   ## This converts the pixel co-ordinates to data values.
        if scaled_series is not None:
            logger.info("Successfully scaled series.")
    except Exception as e:
        print(f"Error scaling series: {str(e)}")
        logger.debug(f"Error scaling series: {str(e)}")
    
    logger.info(f"Successfully scraped time-series from chart at:  {url}, now getting some metadata...")

    try: 
        sel.scrape_metadata()  # Get metadata from various elements on the page that contain information about the series.
        print(f"Got metadata. \n\nSeries tail: {sel.series.tail()} \n\nScraping complete! Happy pirating yo!")
        logger.debug(f"Scraping complete, data series retrieved successfully from chart at: {url}")
        return sel
    except Exception as e:
        print(f"Error scraping chart at: {url}, {str(e)}") 
        return None