from typing import Literal
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.keys import Keys
import time
import pandas as pd

# tedata related imports
from . import utils
from . import logger

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
class TE_Scraper(object):
    """Class for scraping data from Trading Economics website. This is the main workhorse of the module.
    It is designed to scrape data from the Trading Economics website using Selenium and BeautifulSoup.
    It can load a page, click buttons, extract data from elements, and plot the extracted data.

    **Init Parameters:** 

    - driver (webdriver): A Selenium WebDriver object, can put in an active one or make a new one for a new URL.
    - use_existing_driver (bool): Whether to use an existing driver in the namespace. If True, the driver parameter is ignored.
    - browser (str): The browser to use for scraping, either 'chrome' or 'firefox'.
    - headless (bool): Whether to run the browser in headless mode (show no window).
    """

    # Define browser type with allowed values
    BrowserType = Literal["chrome", "firefox"]
    def __init__(self, 
                 driver: webdriver = None, 
                 use_existing_driver: bool = False,
                 browser: BrowserType = "firefox", 
                 headless: bool = True):
        
        self.browser = browser
        self.headless = headless

        active = utils.find_active_drivers() 
        if len(active) <= 1:
            use_existing_driver = False

        if driver is None and not use_existing_driver:
            if browser == "chrome":
                print("Chrome browser not supported yet. Please use Firefox.")
                logger.debug(f"Chrome browser not supported yet. Please use Firefox.")
                return None
                # self.driver = utils.setup_chrome_driver(headless = headless)
            elif browser == "firefox":
                options = webdriver.FirefoxOptions()
                if headless:
                    options.add_argument('--headless')
                self.driver = utils.TimestampedFirefox(options=options)
            else:
                logger.debug(f"Error: Unsupported browser! Use 'chrome' or 'firefox'.")
                raise ValueError("Unsupported browser! Use 'chrome' or 'firefox'.")
            logger.debug(f"New {browser} driver created.")
        elif use_existing_driver:   ## May want to change this later to make sure a scraper doesn't steal the driver from a search object.
            self.driver = active[-1][0]
            logger.debug(f"Using existing {browser} driver.")
        else:
            self.driver = driver
            logger.debug(f"Using supplied driver.")
        
        self.wait = WebDriverWait(self.driver, timeout=10)
        self.start_end = None
    
    def load_page(self, url, wait_time=5):
        """Load page and wait for it to be ready"""

        self.last_url = url
        self.series_name = url.split("/")[-1].replace("-", " ")
        try:
            self.driver.get(url)
            logger.debug(f"Page loaded successfully: {url}")
            logger.info(f"WebPage at {url} loaded successfully.")
            time.sleep(wait_time)  # Basic wait for page load
            self.full_page = self.get_page_source()
            self.page_soup = BeautifulSoup(self.full_page, 'html.parser')
            return True
        except Exception as e:
            print(f"Error loading page: {str(e)}")
            logger.debug(f"Error loading page: {str(e)}")
            return False
    
    def click_button(self, selector, selector_type=By.CSS_SELECTOR):
        """Click button and wait for response..."""

        try:
            # Wait for element to be clickable
            button = self.wait.until(
                EC.element_to_be_clickable((selector_type, selector))
            )
            # Scroll element into view
            #self.driver.execute_script("arguments[0].scrollIntoView(true);", button)
            time.sleep(1)  # Brief pause after scroll
            button.click()
            logger.info("Button clicked successfully, waiting 2s for response...")
            logger.debug(f"Button clicked successfully: {selector}")
            time.sleep(2)
            return True
        except TimeoutException:
            logger.info(f"Button not found or not clickable: {selector}")
            logger.debug(f"Button not found or not clickable: {selector}")
            return False
        except Exception as e:
            logger.info(f"Error clicking button: {str(e)}")
            logger.debug(f"Error clicking button: {str(e)}")
            return False

    def find_max_button(self, selector: str = "#dateSpansDiv"):
        """Find the button on the chart that selects the maximum date range and return the CSS selector for it."""

        try:
            buts = self.page_soup.select_one(selector)
            i = 1
            for res in buts.find_all("a"):
                #print(res.text)
                if res.text.upper() == "MAX":
                    max_selector = res.get("class")
                    if isinstance(max_selector, list):
                        max_selector = max_selector[0]
                    fin_selector = "a." + max_selector + f":nth-child({i})"
                    logger.debug(f"MAX button found for chart at URL: {self.last_url}, selector: {fin_selector}")
                i += 1
            
            return fin_selector
        except Exception as e:
            print(f"Error finding date spans buttons: {str(e)}")
            logger.debug(f"Error finding date spans buttons: {str(e)}")
            return None

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
            logger.debug(f"Element found and assigned to current_element attribute: {selector}")
            return element
        except TimeoutException:
            print(f"Element not found: {selector}")
            logger.debug(f"Element not found: {selector}")
            return None
        except Exception as e:
            print(f"Error finding element: {str(e)}")
            logger.debug(f"Error finding element: {str(e)}")
            return None
        
    def series_from_element(self, element: str = None, invert_the_series: bool = True, return_series: bool = False):
        """Extract series data from element text. This extracts the plotted series from the svg chart by taking the PATH 
        element of the data tarace on the chart. Series values are pixel co-ordinates on the chart.

        **Parameters:**

        - element (str): The element to extract data from. Will use self.current_element if not provided.
        - invert_the_series (bool): Whether to invert the series values.

        **Returns:**

        - series (pd.Series): The extracted series data.
        """

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
            series = utils.invert_series(series, max_val = self.y_axis.index.max())
        self.series = series

        self.pix0 = self.series.iloc[0]; self.pix1 = self.series.iloc[-1]
        logger.debug(f"Raw data series extracted successfully: {series.head()}")
        logger.info(f"Raw data series extracted successfully.")
        if return_series:
            return series
    
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
            logger.debug(f"scale_series method: Start value, end value: {y0}, {y1}, {pix0}, {pix1}, {pix0}, {pix1}")
            
            self.unit_per_px_alt = abs(y1 - y0) / abs(pix1 - pix0)  # Calculated from the start and end datapoints.
            
            if not hasattr(self, "axis_limits"):
                self.axis_limits = self.extract_axis_limits()
            ## Turns out that this formulation below is the best way to calculate the scaling factor for the chart.
            self.axlims_upp = (self.y_axis.iloc[-1] - self.y_axis.iloc[0]) / (self.axis_limits["y_max"] - self.axis_limits["y_min"])

            # if the start and end points are at similar values this will be problematic though. 
            logger.debug(f"Start value, end value: {y0}, {y1}, pix0, pix1: {pix0}, {pix1}, "
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
    
    def get_xlims_from_tooltips(self, force_rerun: bool = False):
        """ Use the get_tooltip class to get the start and end dates and some other points of the time series using the tooltip box displayed on the chart.
        Takes the latest num_points points from the chart and uses them to determine the frequency of the time series. The latest data is used
        in case the earlier data is of lower frequency which can sometimes occurr.
        
        **Parameters:**
        
        - force_rerun (bool): Whether to force a rerun of the method to get the start and end dates and frequency of the time series again. The method
        will not run again by default if done a second time and start_end and frequency attributes are already set. If the first run resulted in erroneous
        assignation of these attributes, set this to True to rerun the method. However, something may need to be changed if it is not working..."""

        if hasattr(self, "tooltip_scraper"):
            pass    
        else: 
            self.tooltip_scraper = utils.get_tooltip(driver=self.driver, chart_x=335.5, chart_y=677.0)  #Note: update this later to use self.width and height etc...
        
        if hasattr(self, "start_end") and self.start_end is not None and hasattr(self, "frequency") and self.frequency is not None and not force_rerun:
            return
        else:
            time.sleep(1)
            data_points, num_points = self.tooltip_scraper.scrape_dates_from_tooltips(num_points=7)
            logger.info(f"Scraped {len(data_points)} data points from the chart, num_points target was {num_points}")
            
            if len(data_points) > num_points:
                logger.debug("Successfully scraped start and end dates plus other data points to determine frequency of the time-series...")
                self.start_end = {
                'start_date': data_points[-1]["date"],
                'end_date': data_points[0]["date"],
                'start_value': data_points[-1]["value"], 
                'end_value': data_points[0]["value"]
                }
                dates = [point["date"] for point in data_points][-2::-1]
                values = [point["value"] for point in data_points][-2::-1]
                self.ripped_points = {"dates": dates, "values": values}

                diff = pd.Series(dates).diff().dropna().mode()[0]
                self.frequency = utils.map_frequency(diff)
                print(f"Time delta between data points in the series appears to be approxiately: {diff.days} days, will use {self.frequency} frequency.")
                logger.debug(f"Time series frequency appears to be: {diff.days}, {self.frequency}")

            else:
                logger.info("Error scraping data from tooltips..")
                logger.debug("Error scraping data from tooltips..")
                return None

    def make_x_index(self, force_rerun: bool = False, return_index: bool = False):
        """Make the DateTime Index for the series using the start and end dates scraped from the tooltips. 
        This does a few things and uses Selenium to scrape the dates from the tooltips on the chart as well as
        some more points to determine the frequency of the time series. It will take some time....
        """
        
        print("Using selenium and toltip scraping to construct the date time index for the time-series, this'll take a bit...")
        self.get_xlims_from_tooltips(force_rerun = force_rerun)

        if self.start_end is not None:
            logger.info(f"Start and end values scraped from tooltips: {self.start_end}")
            logger.debug(f"Start and end values scraped from tooltips: {self.start_end}")
        else:
            print("Error: Start and end values not found...pulling out....")
            logger.debug(f"Error: Start and end values not found...pulling out....")
            return None

        try:
            start_date = self.start_end["start_date"]; end_date = self.start_end["end_date"]
            dtIndex = self.dtIndex(start_date=start_date, end_date=end_date, ser_name=self.series_name)
            #print("Date index created successfully. Take a look at the final series: \n", dtIndex)
            logger.debug(f"Date index created successfully: {dtIndex.index}")
            logger.info(f"Date index created successfully.")
            if return_index:
                return dtIndex.index
        
        except Exception as e:
            print(f"Error creating date index: {str(e)}")
       
    def get_y_axis(self):
        """Get y-axis values from chart to make a y-axis series with tick labels and positions (pixel positions).
        Also gets the limits of both axis in pixel co-ordinates. A series containing the y-axis values and their pixel positions (as index) is assigned
        to the "y_axis" attribute. The "axis_limits" attribute is made too & is  dictionary containing the pixel co-ordinates of the max and min for both x and y axis.
        """

        ##Get positions of y-axis gridlines
        y_heights = []
        self.full_chart = self.get_element(selector = "#chart").get_attribute("outerHTML")
        self.chart_soup = BeautifulSoup(self.full_chart, 'html.parser')  #Make a bs4 object from the #chart element of the page.

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
        self.unit_per_pix = average
        logger.debug(f"Average px per unit for y-axis: {average}")  #Calculate the scaling for the chart so we can convert pixel co-ordinates to data values.

        yaxis = pd.Series(yaxlabs, index = pixheights, name = "ytick_label")
        yaxis.index.rename("pixheight", inplace = True)
        try:
            yaxis = yaxis.astype(int)
        except:
            pass

        self.y_axis = yaxis
        if self.y_axis is not None:
            logger.debug(f"Y-axis values scraped successfully.")
            logger.info(f"Y-axis values scraped successfully.")
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
        if hasattr(self, "frequency"):
            new_ser = new_ser.resample(self.frequency).first()
        else:
            new_ser = new_ser.resample("MS").first()  ## Use First to match the MS freq.
        self.series = new_ser
        return new_ser

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
    
    def plot_series(self, add_horizontal_lines: bool = False):
        """
        Plots the time series data using pandas with plotly as the backend. Plotly is set as the pandas backend in __init__.py for tedata.
        If you want to use matplotlib or other plotting library don't use this method, plot the series attribute data directly. If using jupyter
        you can set 

        :Parameters:
        - add_horizontal_lines (bool): If True, adds horizontal lines and labels to the plot. The lines correspond to the grid on the TE chart.
        The lines are plotted in terms of pixel co-ordinates, not data values, don't use the lines when plotting the final scaled series. Only for 
        inspection of the raw data (pixel co-ordinates) extracted from the #path element of the svg chart on TE.

        :Returns: None
        """

        fig = self.series.plot()  # Plot the series using pandas, plotly needs to be set as the pandas plotting backend.

        if hasattr(self, "series_metadata"):
            title = str(self.series_metadata["country"]).capitalize() + ": " + str(self.series_metadata["title"]).capitalize()
            ylabel = str(self.series_metadata["units"]).capitalize()
        else:
            title = "Time Series Plot"; ylabel = "Value"

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
            title = title
        )
  
        # Show the figure
        fig.show()

    def scrape_metadata(self):
        self.series_metadata = {}
        logger.debug(f"Scraping metadata for the series from the page...")

        try:
            self.series_metadata["units"] = self.chart_soup.select_one('#singleIndChartUnit2').text
        except Exception as e:
            print("Units label not found: ", {str(e)})
            self.series_metadata["units"] = "a.u"
        
        try:
            self.series_metadata["original_source"] = self.chart_soup.select_one('#singleIndChartUnit').text
        except Exception as e:
            print("original_source label not found: ", {str(e)})
            self.series_metadata["original_source"] = "unknown"

        if hasattr(self, "series"):
            if hasattr(self, "page_soup"):
                heads = self.page_soup.select("#ctl00_Head1")
                self.series_metadata["title"] = heads[0].title.text.strip()
            else:
                self.series_metadata["title"] = self.last_url.split("/")[-1].replace("-", " ")  # Use URL if can't find the title
            self.series_metadata["indicator"] = self.last_url.split("/")[-1].replace("-", " ")  
            self.series_metadata["country"] = self.last_url.split("/")[-2].replace("-", " ") 
            self.series_metadata["length"] = len(self.series)
            self.series_metadata["frequency"] = self.frequency  
            self.series_metadata["source"] = "Trading Economics" 
            self.series_metadata["id"] = "/".join(self.last_url.split("/")[-2:])
            self.series_metadata["start_date"] = self.series.index[0].strftime("%Y-%m-%d")
            self.series_metadata["end_date"] = self.series.index[-1].strftime("%Y-%m-%d")
            self.series_metadata["min_value"] = float(self.series.min())
            self.series_metadata["max_value"] = float(self.series.max())
            print("Series metadata: ", self.series_metadata)

        try:
            desc_card = self.page_soup.select_one("#item_definition")
            header_text = desc_card.select_one('.card-header').text.strip()
            if header_text.lower() == self.series_metadata["title"].lower():
                self.series_metadata["description"] = desc_card.select_one('.card-body').text.strip()
            else:
                print("Description card title does not match series title.")
                self.series_metadata["description"] = "Description not found."
        except Exception as e:
            print("Description card not found: ", {str(e)})

        self.metadata = pd.Series(self.series_metadata)
        if self.metadata is not None:
            logger.debug(f"Metadata scraped successfully: {self.series_metadata}")

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
############ Convenience function to run the full scraper from scraper.py ##########################################

def scrape_chart(url: str = "https://tradingeconomics.com/united-states/business-confidence", 
                 id: str = None,
                 country: str = "united-states",
                 scraper: TE_Scraper = None,
                 driver: webdriver = None, 
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
    
    :Parameters:

    - url (str): The URL of the chart to scrape.
    - id (str): The id of the chart to scrape. This is the latter part of the URL after the country name.
    - country (str): The country of the chart to scrape. Default is 'united-states'.
    - scraper (TE_Scraper): A TE_Scraper object to use for scraping the data. If this is passed, the function will not create a new one.
    - driver (webdriver): A Selenium WebDriver object to use for scraping the data. If this is passed, the function will not create a new one. If 
    scraper and driver are both passed, the webdriver of the scraper object will be used rather than the supplied webdriver.
    - headless (bool): Whether to run the browser in headless mode (display no window).
    - browser (str): The browser to use, either 'chrome' or 'firefox'.

    :Returns:  
    - TE_Scraper object with the scraped data or None if an error occurs.
    """

    ## Parameters that monitor progress....
    loaded_page = False; clicked_button = False; yaxis = None; series = None; x_index = None; scaled_series = None; datamax = None; datamin = None

    if scraper is not None:
        sel = scraper
        if driver is None:
            driver = scraper.driver
        else:
            scraper.driver = driver
    else:
        sel = TE_Scraper(driver = driver, browser = browser, headless = headless)

    if id is not None:
        url = f"https://tradingeconomics.com/{country}/{id}"

    if sel.load_page(url):
        logger.info(f"Page at {url} loaded successfully.")
        loaded_page = True
        logger.debug(f"Page loaded successfully {url}")
    else:
        print("Error loading page at: ", url)
        logger.debug(f"Error loading page at: {url}")
        return None

    if sel.click_button(sel.find_max_button()):  ## This is the "MAX" button on the Trading Economics chart to set the chart to max length.
        print("Clicked the MAX button successfully.")
        logger.debug(f"Clicked the MAX button successfully.")
        clicked_button = True
    else:
        print("Error clicking the MAX button.")
        logger.debug(f"Error clicking the MAX button.")
        return None
    
    time.sleep(1)
    try:
        yaxis = sel.get_y_axis()
        print("Successfully scraped y-axis values from the chart:", " \n", yaxis) 
        logger.debug(f"Successfully scraped y-axis values from the chart.") 
    except Exception as e:
        print(f"Error scraping y-axis: {str(e)}")
        logger.debug(f"Error scraping y-axis: {str(e)}")
    
    try:
        sel.get_element()
        series = sel.series_from_element(invert_the_series=True)
        print("Successfully scraped raw pixel co-ordinate series from the path element in chart:", " \n", series)
        time.sleep(1)
    except Exception as e:
        print(f"Error scraping y-axis: {str(e)}")
        logger.debug(f"Error scraping y-axis: {str(e)}")

    try:
        x_index = sel.make_x_index()
        time.sleep(1)
    except Exception as e:
        print(f"Error creating date index: {str(e)}")
        logger.debug(f"Error creating date index: {str(e)}")

    try:
        #datamax, datamin = sel.get_datamax_min()   
        scaled_series = sel.scale_series()   
        logger.info("Successfully scaled series.")    
        logger.debug("Successfully scaled series.") 
    except Exception as e:
        print(f"Error scaling series: {str(e)}")
        logger.debug(f"Error scaling series: {str(e)}")
    
    if loaded_page and clicked_button and yaxis is not None and series is not None and x_index is not None and scaled_series is not None: #and datamax is not None and datamin is not None:
        print("Successfully scraped time-series from chart at: ", url, " \n", sel.series, "now getting some metadata...")
        sel.scrape_metadata()
        print("Check the metadata: ", sel.series_metadata, "\nScraping complete! Happy pirating yo!")
        logger.debug(f"Scraping complete, data series retrieved successfully from chart at: {url}")
        return sel
    else:
        print("Error scraping chart at: ", url) 
        return None