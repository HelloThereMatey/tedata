from typing import Literal
from collections import OrderedDict
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
import time
import datetime
import pandas as pd
import os 
import plotly.graph_objects as go

fdel = os.path.sep
wd = os.path.dirname(__file__)

# tedata related imports
from . import utils
from .base import Generic_Webdriver, SharedWebDriverState

import logging
# Get the logger from the parent package
logger = logging.getLogger('tedata.scraper')

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
    BrowserType = Literal["chrome", "firefox"]  #Chrome still not working as of v0.3.0..
    def __init__(self, **kwargs):
        Generic_Webdriver.__init__(self, **kwargs)
        SharedWebDriverState.__init__(self)
        self.observers.append(self)  # Register self as observer
        self._shared_state = self  # Since we inherit SharedWebDriverState, we are our own shared state

    def load_page(self, url, extra_wait_time=3):
        """Load page and wait for it to be ready"""
        self.last_url = url
        self.series_name = url.split("/")[-1].replace("-", " ")
        
        try:
            # This waits for initial page load
            self.driver.get(url)
            
            # Now explicitly wait for your critical elements
            chart_element = self.wait.until(
                EC.presence_of_element_located((By.ID, "chart")),
                message="Chart element not found after page load")
            
            # Scroll chart into view to ensure it's visible for interactions
            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'auto', block: 'center'});", chart_element)
            time.sleep(0.5)  # Small delay to let scrolling complete

            time.sleep(extra_wait_time)  # Extra wait time after page load just to be sure...
            
            if self.has_no_data_message():
                logger.info("No data found for your country/indicator comibnation, check that the URL or country/indicator combination is correct.")
                #return False
            # Wait for the chart content to be loaded with a shorter timeout
            try:
                WebDriverWait(self.driver, 5).until(  # Using 5 seconds instead of default timeout
                    EC.presence_of_element_located((By.CLASS_NAME, "highcharts-series-group")),
                    message="Chart series not present")
            except TimeoutException:
                logger.info("No data series found for your country/indicator comibnation, check that the URL or country/indicator combination is correct.")
            
            # Now it's safe to get the page source
            self.full_page = self.get_page_source()
            self.page_soup = BeautifulSoup(self.full_page, 'html.parser')
            self.chart_soup = self.page_soup.select_one("#chart")  #Make a bs4 object from the #chart element of the page.
            self.full_chart = self.chart_soup.contents

            #Final check...
            if len(list(self.chart_soup.select_one(".highcharts-series-group").children)) > 0:
                logger.info("Page loaded successfully.")
            else:
                logger.info("Page loaded but no data found.")
                return False
        except Exception as e:
            print(f"Error loading page: {str(e)}")
            logger.debug(f"Error loading page: {str(e)}")
            return False
        
        retries = 4
        for i in range(retries):
            try: 
                if self.create_chart_types_dict(): # Create the chart types dictionary for the chart.
                    break
            except Exception as e:
                logger.debug("Error creating chart types dictionary. Retrying, attempt: ", i)
                continue
        try:
            self.update_date_span()
        except Exception as e:
            logger.info(f"Error determining date span of chart: {str(e)}")
        return True
    
    def has_no_data_message(self):
        """
        Check if the current chart shows a "no data available" message.
        
        Returns:
            bool: True if no data message is displayed, False otherwise
        """
        script = """
        try {
            const noDataMsg = document.querySelector('.noDataPlacehoder p');
            return noDataMsg && 
                noDataMsg.textContent.includes('There is no data for this indicator or it is unavailable at the moment');
        } catch (e) {
            return false;
        }
        """
        
        result = self.driver.execute_script(script)
        if result:
            logger.info("No data message detected on chart")
        
        return True if result else False
    
    def click_button(self, selector, selector_type=By.CSS_SELECTOR):
        """Click button using webdriver and wait for response.
        **Parameters:**
        - selector (str): The CSS selector for the button to click.
        - selector_type (By): The type of selector to use, By.CSS_SELECTOR by default."""

        try:
            # Wait for element to be clickable
            button = self.wait.until(
                EC.element_to_be_clickable((selector_type, selector)))
            
            button.click()
            time.sleep(0.25)
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
            if "selected" in r["class"] and r.text in list(self.date_spans.keys()):
                date_span = {r.text: r}
                return date_span
            else:
                # No button has been slected already in this case.
                shortest_span = list(self.date_spans.keys())[0]
                self.set_date_span(shortest_span)
                return shortest_span

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

        self.custom_date_span_js(start_date="1950-01-01", end_date=datetime.date.today().strftime("%Y-%m-%d"))
        self.date_span = "MAX"

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
        self.date_span = list(self.date_spans.keys())[0]
    
    def create_chart_types_dict(self):
        """Create a dictionary of chart types and their CSS selectors. This is used to select the chart type on the Trading Economics chart.
        The dictionary is stored in the chart_types attribute of the class. The keys are the names of the chart types and the values are the CSS selectors
        for the chart type buttons on the chart."""
        try:
            hart_types = self.chart_soup.select_one(".chartTypesWrapper")
            self.chart_types = {child["title"]: "."+child["class"][0]+" ."+ child.button["class"][0] for child in hart_types.children}
            for key, value in self.chart_types.items():
                self.chart_types[key] = value.split(" ")[0]
            logger.info(f"Chart types dictionary created successfully: {self.chart_types.keys()}")
            return True
        except Exception as e:
            logger.error(f"Error creating chart types dictionary: {e}")
            return False

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
        
        selector = f"#chart.chart_module.chart1.undertaker-section div.chart_preview.undertaker_chart.logic-new-charts-no div.hawk-totalWrapper div.hawk-header\
          div.topnav-flex-container div.pickChartTypes div.PREselectedChartType div.chartTypesWrapper.dropDownStyle div{self.chart_types[chart_type]} button.dkLabels-label-btn"
        
        if chart_type in self.chart_types.keys():
            if self.click_button("#chart > div > div > div.hawk-header > div > div.pickChartTypes > div > button"):
                time.sleep(1.5)
                if self.click_button(selector):
                    self.chart_type = self.chart_types[chart_type]
                    logger.info(f"Chart type set to: {chart_type}")
                    self.update_chart()
                    return True
                else:
                    logger.info(f"Error selecting chart type: {chart_type}")
                    return False
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

    def set_chartType_js(self, chart_type: Literal['Column', 'Spline', 'Areaspline', 'Stepline', 'Line', 'Area']):
        """Set the chart type using javascript. This is a more robust method of setting the chart type than using the click_button method.
        The click_button method can sometimes fail to click the chart type button. This method will set the chart type using javascript and will
        update the chart_type attribute of the class to reflect the new chart type.

        **Parameters:**
        - chart_type (Literal): The chart type to set. This should be one of the keys of the chart_types dictionary attribute of the class. The 
        options are 'Column', 'Spline', 'Areaspline', 'Stepline', 'Line', 'Area'.
        """
        
        success = self.driver.execute_script(f"""
                var chartType = "{chart_type}";
                var buttons = document.querySelectorAll('.chartTypesWrapper button');
                for (var i = 0; i < buttons.length; i++) {{
                    if (buttons[i].textContent.trim() === chartType || 
                        buttons[i].getAttribute('title') === chartType ||
                        buttons[i].parentElement.getAttribute('title') === chartType) {{
                        buttons[i].click();
                        return true;
                    }}
                }}
                return false;
            """)
            
        if success:
            self.chart_type = self.chart_types[chart_type]
            logger.info(f"Chart type set to: {chart_type} (using JavaScript)")
            time.sleep(0.5)
            self.update_chart()
            return True
        else:
            logger.info(f"Error setting chart type: {chart_type} (using JavaScript)")
            return False   
    
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
        
    def series_from_chart_soup(self, selector: str = ".highcharts-graph", 
                               invert_the_series: bool = False, 
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

        if self.chart_type != self.chart_types[use_chart_type]:
            self.set_chartType_js(use_chart_type) ## Use a certain chart type for the extraction of the series data. May fail with certain types of charts.

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
        logger.debug(f"Raw data series extracted successfully.")
        self.series_extracted_from = use_chart_type  #Add this attribute so that the apply_x_index method knows which chart_type the series came from.
        
        #Add translate to the series to yield the proper y-values
        transform = self.chart_soup.select_one(".highcharts-graph").parent["transform"].split(" ")
        translate = transform[0].replace("translate(","").replace(")", "").split(",")
        translate = [float(x) for x in translate]
        self.other_transforms = transform[1:]
        self.transform = translate

        series = series + translate[1]
        self.series = series
        self.raw_path_series = series.copy()
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
        
    def custom_date_span_js(self, start_date: str = "1900-01-01", end_date: str = datetime.date.today().strftime("%Y-%m-%d")) -> bool:
        """Set the date range on the active chart in the webdriver window using JavaScript.
        This is more reliable than using Selenium's send_keys and can avoid issues with focus.
        
        Args:
            start_date (str): Start date in format YYYY-MM-DD
            end_date (str): End date in format YYYY-MM-DD
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Load JavaScript code from file
            js_file_path = os.path.join(os.path.dirname(__file__), 'custom_datespan.js')
            with open(js_file_path, 'r') as file:
                js_code = file.read()
            
            # Execute the JavaScript with parameters using async API (custom_datespan.js expects a callback)
            result = self.driver.execute_async_script(js_code, start_date, end_date)
            
            if isinstance(result, dict) and result.get('success'):
                # Set date span in our object
                self.date_span = {"Custom": {"start_date": start_date, "end_date": end_date}}
                self.update_chart()
                
                logger.info(f"Date span set to custom range: {start_date} to {end_date} (using JavaScript)")
                return True
            else:
                error_msg = result.get('error', 'Unknown error') if isinstance(result, dict) else 'Unknown error'
                logger.info(f"Failed to set date span using JavaScript: {error_msg}")
                return False
            
        except Exception as e:
            logger.info(f"Error executing custom_date_span_js: {e}")
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
            
        if not hasattr(self, "axis_limits"):
            self.axis_limits = self.extract_axis_limits()
        ymin = self.axis_limits['y_min']; ymax = self.axis_limits['y_max']
        ## Turns out that this formulation below is the best way to calculate the scaling factor for the chart.
        unit_range = self.y_axis.iloc[-1] - self.y_axis.iloc[0]
        pxrange = self.y_axis.index[0] - self.y_axis.index[-1]
        self.axlims_upp = unit_range/pxrange
        print(f"Unit per pix forumlation, {self.y_axis.iloc[-1]}, {self.y_axis.iloc[0]}, {unit_range}, {pxrange}, {ymax}, {ymin}, {self.axlims_upp}")

        # if the start and end points are at similar values this will be problematic though. 
        logger.info("Scale series method:  \n"
                        f"unit_per_pix calculated from the y axis ticks: {self.unit_per_pix}, \n"
                        f"unit_per_pix from axis limits and self.y_axis (probably best way): {self.axlims_upp}\n"
                        f"yaxis top tick: {self.y_axis.iloc[-1]}, yaxis bot tick: {self.y_axis.iloc[0]}\n"
                        f"axis_limits: {ymin}, {ymax}, y-axis series min & max pixel values: {self.y_axis.index[0]}, {self.y_axis.index[-1]}")

        ##Does the Y axis cross zero? Where is the zero point??
        self.x_intercept_px = utils.find_zero_crossing(self.y_axis)
        print("Series crosses zero, x-axis should be at about pixel y-cordinate: ", self.x_intercept_px)

        unscaled = self.unscaled_series.copy()
        # Calculate the series in vector fashion
        self.series = (self.y_axis.index[0] - unscaled)*self.axlims_upp + self.y_axis.iloc[0]

        if hasattr(self, "metadata"):
            self.metadata["start_date"] = self.series.index[0].strftime("%Y-%m-%d")
            self.metadata["end_date"] = self.series.index[-1].strftime("%Y-%m-%d")
            self.metadata["min_value"] = float(self.series.min())
            self.metadata["max_value"] = float(self.series.max())
            self.metadata["length"] = len(self.series)
            self.series_metadata = pd.Series(self.metadata)
        else:
            print("start_end not found, run get_datamax_min() first.")
            logger.debug("start_end not found, run get_datamax_min() first.")
            return

        return self.series
    
    def get_chart_dims(self):
        """Get dimensions of chart and plotting area"""
        try:
            # Ensure full_chart is WebElement
            self.chart_element = self.driver.find_element(By.CSS_SELECTOR, "#chart")
            # Get overall chart dimensions
            self.chart_rect = {k: round(float(v), 1) for k, v in self.chart_element.rect.items()}
            
            # Get plot area dimensions
            self.plot_background = self.driver.find_element(By.CSS_SELECTOR, '.highcharts-plot-background')
            self.axes_rect = {k: round(float(v), 1) for k, v in self.plot_background.rect.items()}
            self.chart_x = self.axes_rect["width"]
            self.chart_y = self.axes_rect["height"]
            return True
        
        except Exception as e:
            print(f"Failed to get chart dimensions: {e}")
            logger.error(f"Failed to get chart dimensions: {e}")
            return False
    
    def get_xlims_from_tooltips(self, set_max_datespan: bool = True):
        """ Use the TooltipScraper class to get the start and end dates and some other points of the time series using the tooltip box displayed on the chart.
        Takes the latest num_points points from the chart and uses them to determine the frequency of the time series. The latest data is used
        in case the earlier data is of lower frequency which can sometimes occurr.
        
        **Parameters:**
        
        - force_rerun (bool): Whether to force a rerun of the method to get the start and end dates and frequency of the time series again. The method
        will not run again by default if done a second time and start_end and frequency attributes are already set. If the first run resulted in erroneous
        assignation of these attributes, set this to True to rerun the method. However, something may need to be changed if it is not working..."""

        print("get_xlims_from_tooltips method: date_span: ", self.date_span, ", chart_type:", self.chart_type)

        if set_max_datespan:
            self.set_max_date_span_viaCalendar()  ##Set date_span to MAX for start and end date pull...
            time.sleep(0.5)
        self.update_chart()
        self.set_chartType_js("Spline") #Force spline chart selection - very important. I still have no way to determine if the chart type has changed when it changes automatically.
        #Chart type must be spline or line for this to work. Sometimes the chart_type chnages automatically when datespan is altered.

        if not hasattr(self, "tooltip_scraper"):
            self.tooltip_scraper = utils.TooltipScraper(parent_instance = self) # Create a tooltip scraper child object
        
        time.sleep(1)
        self.start_end = self.tooltip_scraper.first_last_dates()
        if self.start_end is None or pd.isna(self.start_end["start_date"]) or pd.isna(self.start_end["end_date"]):
            self.start_end = self.tooltip_scraper.first_last_dates()
        print("Start and end dates scraped from tooltips: ", self.start_end)
        if hasattr(self, "metadata"):
            self.metadata["unit_tooltips"] = self.start_end["unit_str"]

    def make_x_index(self, force_rerun_xlims: bool = True, force_rerun_freqdet: bool = True):
        """Make the DateTime Index for the series using the start and end dates scraped from the tooltips. 
        This uses Selenium and also scrapes the some of the latest datapoints from the tooltips on the chart in order to determine
        the frequency of the time series. It will take a bit of time to run.

        **Parameters:**
        - force_rerun_xlims (bool): Whether to force a rerun of the method to get the start and end dates and frequency of the time series again. The method
        will not run again by default if done a second time and start_end and frequency attributes are already set. 
        - force_rerun_freqdet (bool): Whether to force a rerun of the method to get the frequency of the time series again. The method
        will not run again by default if done a second time and frequency attribute is already set. 
        """
        
        if not hasattr(self, "tooltip_scraper"):  # If the tooltip scraper object is not already created, create it.
            self.tooltip_scraper = utils.TooltipScraper(parent_instance = self) # Create a tooltip scraper child object

        print("Using selenium and tooltip scraping to construct the date time index for the time-series, this'll take a bit...")
        ## Get the latest 10 or so points from the chart, date and value from tooltips, in order to determine the frequency of the time series.
        if force_rerun_freqdet or not hasattr(self, "latest_points"):
            #datapoints = self.tooltip_scraper.get_latest_points(num_points = 5)  # Python version, slow
            datapoints = self.tooltip_scraper.latest_points_js(num_points=10)  # js version, faster
            self.latest_points = datapoints
            # Convert metric prefixes for the values in each datapoint
            for point in self.latest_points:
                point["value"] = utils.extract_and_convert_value(point["value"])[0]
                point["date"] = utils.ready_datestr(point["date"])
            latest_dates = [point["date"] for point in datapoints]
            #print("Latest dates: ", latest_dates)

            ## Get the frequency of the time series
            self.date_series = pd.Series(latest_dates[::-1]).astype("datetime64[ns]")
            self.frequency = utils.get_date_frequency(self.date_series)
            if hasattr(self, "metadata"):
                self.metadata["frequency"] = self.frequency
        print("Frequency of time-series: ", self.frequency)

        time.sleep(0.25)

        if force_rerun_xlims or not hasattr(self, "start_end"):
            self.start_end = None
            self.set_max_date_span_viaCalendar()  ##Set date_span to MAX for start and end date pull...
            time.sleep(0.25)
            self.set_chartType_js("Spline") #Force spline chart selection - very important. I still have no way to determine if the chart type has changed when it changes automatically.
            time.sleep(0.25)
            retries = 3
            for i in range(retries):
                self.start_end = self.tooltip_scraper.first_last_dates_js()
                # Check if start_end is None or if any of the four essential keys have None/NaN values
                if (self.start_end is None or 
                    not all(key in self.start_end for key in ["start_date", "end_date"]) or
                    any(pd.isna(self.start_end[key]) for key in ["start_date", "end_date"]))\
                    or any(self.start_end[key] is None for key in ["start_date", "end_date"]):
                    #print("Retrying start_end extraction...")
                    time.sleep(0.25)
                    pass
                else:
                    break
            #For some reason running it twice seems to work better...

            if self.start_end is not None:
                logger.info(f"Start and end values scraped from tooltips: \n{self.start_end}")
                start_date = self.start_end["start_date"]; end_date = self.start_end["end_date"]
                dtIndex = self.dtIndex(start_date=start_date, end_date=end_date, ser_name = self.metadata["title"])
                if dtIndex is not None:
                    logger.info(f"DateTimeIndex created successfully for the time-series.")
                    self.x_index = dtIndex
                    return dtIndex  
                else:
                    logger.info(f"Error creating DateTimeIndex for the time-series.")
                    return None
            else:
                print("Error: Start and end values not found...pulling out....")
                logger.debug(f"Error: Start and end values not found...pulling out....")
                return None
    
    def get_earliest_points(self, num_points: str = "all", num_years: int = 10):
        """Get the earliest data points from the chart using the cursor, use this to check for series that have differing frequency
        at start and end."""

        if not hasattr(self, "start_end"):
            self.get_xlims_from_tooltips()
        if not hasattr(self, "tooltip_scraper"):
            self.tooltip_scraper = utils.TooltipScraper(parent_instance = self)
        
        yearslater = utils.n_years_later(date = self.start_end["start_date"].strftime("%Y-%m-%d"), n_years = num_years)
        self.custom_date_span_js(start_date=self.start_end["start_date"].strftime("%Y-%m-%d"), end_date = yearslater)

        try:
            datapoints = self.tooltip_scraper.latest_points_js(num_points=num_points, force_shortest_span=False, wait_time=5)
            self.early_series = pd.Series([utils.extract_and_convert_value(value["value"])[0] for value in datapoints][::-1], \
                                    index = pd.DatetimeIndex([utils.ready_datestr(date["date"]) for date in datapoints][::-1]), name = self.metadata["title"]).astype(float)
        except Exception as e:
            logger.info("Error getting earliest points: ", e)
            return None

        return self.early_series

    def full_series_fromTooltips(self, set_max_datespan: bool = False):
        """Scrape the full series from the dates and values displayed on the tooltips as the cursor is dragged across the chart. Uses javscript to handle the cursor 
        movement and tooltip retrieval and parsing. This is way faster than using a python loop. I suspect this may end up missing some points for series that 
        have many datapoints. However, it has worked for all series tested thus far. Assigns the resultant series to the series attribute.
        """

        if set_max_datespan:
            print("Setting max date span using calendar...")
            self.set_max_date_span_viaCalendar()
        self.set_chartType_js("Spline") # Force spline chart type so that Y position of cursor does not matter for tooltip retrieval.

        if not hasattr(self, "tooltip_scraper"):
            self.init_tooltipScraper()  ## Initialize the tooltip scraper.
        ## Javascript based method here.
        try:
            datapoints = self.tooltip_scraper.latest_points_js(num_points="all", force_shortest_span=False, wait_time=5)
        except Exception as e:
            logger.info("Tooltip scraping of full series has failed, error: ", e)
            return None
        #Powerful one line pandas connversion...
        self.series = pd.Series([utils.extract_and_convert_value(value["value"])[0] for value in datapoints][::-1], \
                                index = pd.DatetimeIndex([utils.ready_datestr(date["date"]) for date in datapoints][::-1]), name = self.metadata["title"]).astype(float)

        # Add some more metadata about the series. 
        if hasattr(self, "metadata"):
            self.metadata["start_date"] = self.series.index[0].strftime("%Y-%m-%d")
            self.metadata["end_date"] = self.series.index[-1].strftime("%Y-%m-%d")
            self.metadata["min_value"] = float(self.series.min())
            self.metadata["max_value"] = float(self.series.max())
            self.metadata["length"] = len(self.series)
            if hasattr(self, "frequency"):
                self.metadata["frequency"] = self.frequency
            else:
                freq = pd.infer_freq(self.series.index) # Infer the frequency of the series.
                if freq is None:
                    freq = "Unknown/irregular"
                self.metadata["frequency"] = freq
            self.series_metadata = pd.Series(self.metadata)
        logger.info("Successfully scraped full series from tooltips.")
        if self.metadata["frequency"] == "Unknown/irregular":
            logger.info("Frequency of the series is unknown or irregular, the tooltip scraping may have missed points. Retry scraping using 'path' method instead of 'tooltips'.")
        return self.series

    def tooltip_multiScrape(self):
        """ Use the TooltipScraper object to scrape the full series from the chart. This is the most accurate method of scraping the full
        series but s the slowest. The x_index attribute must be set before running this method. The method will use multiple runs
        of the javascript tooltip scraping script. It will be done in multiple runs to prevent points being missed. Number of runs
        will depend upon the length of the x_index attribute. """

        if not hasattr(self, "tooltip_scraper"):
            self.init_tooltipScraper()
        if not hasattr(self, "x_index"):
            self.make_x_index(force_rerun_freqdet=True, force_rerun_xlims=True)

        max_chunk_size = 500  # Maximum number of points to scrape in one go. This is deterined by the density of datapoints on the chart. 
        total_len = len(self.x_index) # Total number of points in the x_index attribute.
        numscrapes = (total_len + max_chunk_size - 1) // max_chunk_size  # Ceiling division
        sub_indexes = []  #The index will be brken up into this list of subIndexes.
        base_size = total_len // numscrapes
        remainder = total_len % numscrapes
        logger.info(f" Using mixed scraping approach, slowest, highest accuracy. Splitting x_index into subIndexes\
        Total points: {total_len}, Max chunk size: {max_chunk_size}, Number of chunks: {numscrapes}, remainder: {remainder}")

        for i in range(numscrapes):
            start_idx = i * base_size
            # For last chunk, include all remaining points
            end_idx = (i + 1) * base_size if i < numscrapes - 1 else total_len
            sub_indexes.append(self.x_index[start_idx:end_idx])

        logger.info(f"x_index Start date: {self.x_index[0]}, End date: {self.x_index[-1]}")
        for i, idx in enumerate(sub_indexes): #Chec
            logger.info(f"SubIndex {i}: {len(idx)} points, from {idx[0]} to {idx[-1]}, frequency: {pd.infer_freq(idx)}")
            #Set the date span on the chart to cover the subIndex.
            if i == len(sub_indexes) - 1:
                end_date = datetime.date.today().strftime("%Y-%m-%d")
            else:
                end_date = idx[-1].strftime("%Y-%m-%d")
            self.custom_date_span_js(start_date=idx[0].strftime("%Y-%m-%d"), end_date = end_date)
            self.set_chartType_js("Spline") #Force spline chart selection - needed for tootip capture

            try:
                datapoints = self.tooltip_scraper.latest_points_js(num_points="all", force_shortest_span=False, wait_time=1)
                #Powerful one line pandas connversion...
                series = pd.Series([utils.extract_and_convert_value(value["value"])[0] for value in datapoints][::-1], \
                                    index = pd.DatetimeIndex([utils.ready_datestr(date["date"]) for date in datapoints][::-1]), name = self.metadata["title"]).astype(float)
            except Exception as e:
                logger.info("Tooltip scraping of full series has failed, error: ", e)
                return None
            
            if i == 0:
                self.series = series
            else:
                self.series = pd.concat([self.series, series], axis = 0).rename(self.metadata["title"])

        if hasattr(self, "metadata"):
            self.metadata["start_date"] = self.series.index[0].strftime("%Y-%m-%d")
            self.metadata["end_date"] = self.series.index[-1].strftime("%Y-%m-%d")
            self.metadata["min_value"] = float(self.series.min())
            self.metadata["max_value"] = float(self.series.max())
            self.metadata["length"] = len(self.series)
            self.series_metadata = pd.Series(self.metadata)

        ##Sometimes the first and last data points seem to be missed, luckily we have them already in the start_end attribute.
        # Overwrite the first and last points with the start_end values.
        if hasattr(self, "start_end"):
            # Convert start_date and end_date to datetime objects
            start_date = pd.to_datetime(self.start_end["start_date"])
            end_date = pd.to_datetime(self.start_end["end_date"])
            # Create Series objects for the start and end values
            start_series = pd.Series({start_date: self.start_end["start_value"]})
            end_series = pd.Series({end_date: self.start_end["end_value"]})
            # Concatenate with the existing series
            self.series = pd.concat([start_series, self.series, end_series])
            # Drop duplicates keeping the last occurrence (which would be from start_end if dates already exist)
            self.series = self.series[~self.series.index.duplicated(keep='last')]
            # Sort by index to ensure the datetime index is in ascending order
            self.series = self.series.sort_index().rename(self.metadata["title"])
        logger.info("Successfully scraped full series from tooltips.")
        return True
    
    def series_from_highcharts(self):
        """Get the series data from the Highcharts JavaScript object. This is the fastest method of getting the series data from the chart.
        The series data is stored in the "series" attribute of the class. The method
        will return the series data as well. """

        js_file_path = wd + fdel + 'check_highcharts.js'
        with open(js_file_path, 'r') as file:
            script = file.read()

        try:
            # Use async execution so the JS can call the Selenium callback with the full object
            result = self.driver.execute_async_script(script)
            # If the page returned a JSON string, parse it
            try:
                if isinstance(result, str):
                    import json as _json
                    result = _json.loads(result)
            except Exception as _e:
                print('CHECK_HC_PARSE_ERROR:', _e)
            # Ensure result is a dict and has seriesData
            if not isinstance(result, dict) or 'seriesData' not in result:
                raise ValueError(f'check_highcharts returned unexpected payload: {repr(result)}')

            # Extract the data points
            data_points = result['seriesData'][0]['points']
            data = [(point['x'], point['y']) for point in data_points]
            df = pd.DataFrame(data, columns=['timestamp', 'value'])
            # Convert timestamp to datetime
            df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
            # Set date as index
            df = df.set_index('date')

            series = df['value'].rename(self.metadata["title"])
            self.series = series
            logger.info("Successfully extracted series data from Highcharts.")
            freq = pd.infer_freq(self.series.index) # Infer the frequency of the series.
            if freq is None:
                freq = "Unknown/irregular"
            self.metadata["frequency"] = freq
            self.metadata["start_date"] = self.series.index[0].strftime("%Y-%m-%d")
            self.metadata["end_date"] = self.series.index[-1].strftime("%Y-%m-%d")
            self.metadata["min_value"] = float(self.series.min())
            self.metadata["max_value"] = float(self.series.max())
            self.metadata["length"] = len(self.series)
            self.series_metadata = pd.Series(self.metadata)
            
            return series
        except Exception as e:
            logger.info(f"Error extracting series from Highcharts: {e}")
            return None

    def get_chart_type_from_highcharts(self):
        """
        Get the chart type directly from the Highcharts API.
        This is the most reliable way to determine chart type.
        
        Returns:
            dict: Chart type information including main type, series types, and point count
        """
        script = """
        try {
            if (typeof Highcharts === 'undefined') {
                return { error: "Highcharts not found", success: false };
            }
            
            const chart = Highcharts.charts.find(c => c && c.series && c.series.length > 0);
            if (!chart) {
                return { error: "No valid chart found", success: false };
            }
            
            return {
                mainType: chart.options?.chart?.type || "unknown",
                seriesTypes: chart.series.map(s => ({
                    name: s.name,
                    type: s.type || chart.options?.chart?.type
                })),
                pointCount: chart.series[0]?.points?.length || 0,
                success: true
            };
        } catch (e) {
            return { error: "JavaScript error: " + e.message, success: false };
        }
        """
        
        try:
            result = self.driver.execute_script(script)
            if result is None:
                logger.info("JavaScript execution returned None - Highcharts API may not be accessible")
                return None
                
            print('Result: ', result)
            if result.get('success', False):
                self.chart_type = "."+result['seriesTypes'][0]['type']+"Chart"
                logger.info(f"Chart type detected from Highcharts API: {self.chart_type}")
                return result
            else:
                error_msg = result.get('error', 'Unknown error')
                logger.info(f"Failed to detect chart type: {error_msg}")
                return None
        except Exception as e:
            logger.info(f"Error detecting chart type: {e}")
            return None
        
    def set_chartType_highcharts(self, chart_type: Literal['Column', 'Spline', 'Areaspline', 'Stepline', 'Line', 'Area']):
        """Set chart type directly using Highcharts API, unsure if this is working properly yet. This should be the most reliable way to set the chart type.
        List chart types: 'Column', 'Spline', 'Areaspline', 'Stepline', 'Line', 'Area', list them by veiwing chart_types attribute of the TE_Scraper."""
        
        script = f"""
        (() => {{
        if (typeof Highcharts === 'undefined') return false;
        
        const chart = Highcharts.charts.find(c => c && c.series && c.series.length > 0);
        if (!chart) return false;
        
        // Store current type
        const currentType = chart.options?.chart?.type;
        
        // Set new type for all series
        chart.update({{ chart: {{ type: '{chart_type.lower()}' }} }});
        
        return true;
        }})();
        """
        
        success = self.driver.execute_script(script)
        
        if success:
            self.chart_type = chart_type
            logger.info(f"Chart type set to: {chart_type} (using Highcharts API)")
            time.sleep(0.5)
            self.update_chart()
            return True
        else:
            logger.info(f"Error setting chart type: {chart_type} (using Highcharts API)")
            return False
    
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
        y_heights = sorted(y_heights, reverse=True)
        print("y_heights: ", y_heights)

        ##Get y-axis labels
        yax = self.chart_soup.select('g.highcharts-axis-labels.highcharts-yaxis-labels')
        textels = yax[1].find_all('text')

        # Replace metrc prefixes:
        yaxlabs = [utils.extract_and_convert_value(text.get_text())[0] if text.get_text().replace(',','').replace('.','').replace('-','').replace(' ','').isalnum() else text.get_text() for text in textels]
        logger.debug(f"y-axis labels: {yaxlabs}")

        # convert to float...
        if any(isinstance(i, str) for i in yaxlabs):
            yaxlabs = [float(''.join(filter(str.isdigit, i.replace(",", "")))) if isinstance(i, str) else i for i in yaxlabs]
        pixheights = [float(height) for height in y_heights]
        print("pixheights: ", pixheights)

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
            logger.info(f"Y-axis values scraped successfully.")
        else:
            logger.info(f"Y-axis values not scraped successfully, yaxis is None.")
            return None
        
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
        if hasattr(self, "x_index"):
            logger.info("Overwriting existing x_index attribute.")
            self.x_index = None
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
            self.unscaled_series = new_ser.copy()
            if hasattr(self, "metadata"):
                self.metadata["frequency"] = self.frequency  # Update the frequency in the metadata.
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
                'y_min': ylims[1],
                'y_max': ylims[0]
            }
            
            return axis_limits
        except Exception as e:
            print(f"Error extracting axis limits: {str(e)}")
            logger.debug(f"Error extracting axis limits: {str(e)}")
            return None
    
    def plot_series(self, series: pd.Series = None, 
                    annotation_text: str = None, 
                    dpi: int = 300, 
                    ann_box_pos: tuple = (0, - 0.2),
                    show_fig: bool = True,
                    return_fig: bool = False,
                    invert_yaxis: bool = False, **layout_updates):
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
            frequency = self.metadata["frequency"] if "frequency" in self.metadata.keys() else "Unknown"
            if annotation_text is None:
                annotation_text = (
                    f"Source: {self.metadata['source']}<br>"
                    f"Original Source: {self.metadata['original_source']}<br>"
                    f"Frequency: {frequency}<br>"
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

           # Add y-axis inversion if requested
        if invert_yaxis:
            layout_updates['yaxis'] = dict(
                autorange='reversed'  # This inverts the y-axis
            )

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
        
            # Update the layout
        fig.update_layout(**layout_updates)

        # Show the figure
        self.plot = fig
        if show_fig:
            fig.show()
        if return_fig:
            return fig

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
        if not hasattr(self, "plot"):
            logger.info("Error: Plot not found. Run plot_series() method to create a plot.")
            return False

        if format == "html":
            self.plot.write_html(f"{save_path}{fdel}{filename}.html")
            logger.info(f"Plot saved as {save_path}{fdel}{filename}.html")
        else:
            self.plot.write_image(f"{save_path}{fdel}{filename}.{format}", format=format, scale=dpi/100, width = 1400, height = 500)
            logger.info(f"Plot saved as {filename}")
        return True


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

        if hasattr(self, "page_soup"):
            heads = self.page_soup.select("#ctl00_Head1")
            self.metadata["title"] = heads[0].title.text.strip()
        else:
            self.metadata["title"] = self.last_url.split("/")[-1].replace("-", " ")  # Use URL if can't find the title
        self.metadata["indicator"] = self.last_url.split("/")[-1].replace("-", " ")  
        self.metadata["country"] = self.last_url.split("/")[-2].replace("-", " ") 
        self.metadata["source"] = "Trading Economics" 
        self.metadata["id"] = "/".join(self.last_url.split("/")[-2:])
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

    def export_data(self, savePath: str = os.getcwd(), filename: str = None):
        """ Export the series data to an excel .xlsx file. The series and metadata attributes must be set before running this method.
        Only do it after scraping the series data. The metadata will be saved in a separate sheet in the same file.
        
        **Parameters**
        - savePath (str): The directory to save the file to. Default is the current working directory.
        - filename (str): The name of the file to save the data to. Default is the name of the series. """
        
        if not hasattr(self, "series"):
            print("No series found. Run the series_from_chart_soup method first.")
            return None
        if filename is None:
            filename = self.series_name

        with pd.ExcelWriter(f"{savePath}{fdel}{filename}.xlsx") as writer:
            self.series.to_excel(writer, sheet_name='Data')
            self.series_metadata.to_excel(writer, sheet_name='Metadata')
            logger.info(f"Data exported to {savePath}{fdel}{filename}")

    def get_page_source(self):
        """Get current page source after interactions"""
        return self.driver.page_source
    
    def close(self):
        """Clean up resources completely by closing the WebDriver and removing references"""
        try:
            # First try graceful close with quitting the driver
            if hasattr(self, "driver") and self.driver:
                try:
                    # Close all windows/tabs first
                    self.driver.close()
                except Exception as e:
                    logger.debug(f"Error closing window: {str(e)}")
                    pass
                
                # Then quit the driver completely with error handling for connection issues
                try:
                    from selenium.common.exceptions import WebDriverException
                    from urllib3.exceptions import MaxRetryError, NewConnectionError
                    
                    try:
                        self.driver.quit()
                    except (WebDriverException, MaxRetryError, NewConnectionError, ConnectionRefusedError) as e:
                        logger.debug(f"Connection error when quitting driver (this is normal if browser crashed): {str(e)}")
                    except Exception as e:
                        logger.debug(f"Error quitting driver: {str(e)}")
                finally:
                    # Clear the reference regardless of success
                    self.driver = None
            
            # Also close any tooltip_scraper drivers if they exist
            if hasattr(self, "tooltip_scraper") and self.tooltip_scraper:
                if hasattr(self.tooltip_scraper, "driver") and self.tooltip_scraper.driver and self.tooltip_scraper.driver != self.driver:
                    try:
                        self.tooltip_scraper.driver.quit()
                    except Exception:
                        pass
                    self.tooltip_scraper.driver = None
            
            # Clear any large data attributes to help garbage collection
            large_attributes = ["series", "trace_path_series", "full_page", "page_soup", 
                            "chart_soup", "full_chart", "plot"]
            
            for attr in large_attributes:
                if hasattr(self, attr):
                    setattr(self, attr, None)
                    
            # Force garbage collection
            import gc
            gc.collect()
            
            logger.info("Scraper resources successfully released")
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()