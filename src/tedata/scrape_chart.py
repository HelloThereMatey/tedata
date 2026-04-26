import os 
fdel = os.path.sep
wd = os.path.dirname(__file__)
import datetime

from typing import Literal
import time
from selenium import webdriver
# tedata related imports
from . import logger
from .scraper import TE_Scraper

import logging
# Get the logger from the parent package
logger = logging.getLogger('tedata.scrape_chart')

############################################################################################################
############ Helper: click 10Y on commodity chart (uses menu2-bottom selector) ###########################

def _click_10y_button(driver, logger):
    """Click the 10Y date button on commodity charts.
    Commodity charts use #trading_chart > div > div.iChart-wrapper-footer > div.iChart-menu2-bottom-cnt-horizontal
    instead of the standard #dateSpansDiv. Tries the menu2-bottom container first, then falls back to #dateSpansDiv.
    Returns True if 10Y was successfully clicked, False otherwise."""
    ten_years_ago = (datetime.date.today() - datetime.timedelta(days=10*365)).strftime("%Y-%m-%d")
    today_str = datetime.date.today().strftime("%Y-%m-%d")

    # ── Step 1: Try the commodity/menu2-bottom container ──────────────────────────
    success = driver.execute_script("""
        const container = document.querySelector('#trading_chart > div > div.iChart-wrapper-footer > div.iChart-menu2-bottom-cnt-horizontal');
        if (!container) return {clicked: false, via: null, buttons: []};
        const allBtns = container.querySelectorAll('div, span, a, button');
        const textBtns = Array.from(allBtns).filter(el => el.children.length === 0 && el.textContent.trim());
        const tenY = textBtns.find(b => b.textContent.trim() === '10Y');
        if (tenY) { tenY.click(); return {clicked: true, via: 'menu2-bottom', buttons: ['10Y']}; }
        // Try direct text match on any descendant
        const allText = Array.from(container.querySelectorAll('*')).filter(el => el.children.length === 0 && el.textContent.trim() === '10Y');
        if (allText.length > 0) { allText[0].click(); return {clicked: true, via: 'menu2-bottom-text', buttons: ['10Y']}; }
        return {clicked: false, via: 'menu2-bottom', buttons: textBtns.map(b => b.textContent.trim())};
    """)
    if success and success.get('clicked'):
        logger.info("Clicked 10Y via menu2-bottom commodity selector")
        time.sleep(3)
        return True

    logger.info(f"menu2-bottom 10Y not found, available in that zone: {success.get('buttons', []) if success else 'N/A'}")

    # ── Step 2: Fall back to #dateSpansDiv (standard charts) ────────────────────
    success = driver.execute_script("""
        const dateSpansDiv = document.querySelector('#dateSpansDiv');
        if (!dateSpansDiv) return {clicked: false, via: null, buttons: []};
        const buttons = dateSpansDiv.querySelectorAll('a');
        const available = [];
        buttons.forEach(btn => available.push(btn.textContent.trim()));
        const tenY = Array.from(buttons).find(a => a.textContent.trim() === '10Y');
        if (tenY) { tenY.click(); return {clicked: true, via: 'dateSpansDiv', buttons: available}; }
        return {clicked: false, via: 'dateSpansDiv', buttons: available};
    """)
    if success and success.get('clicked'):
        logger.info("Clicked 10Y via standard #dateSpansDiv")
        time.sleep(3)
        return True

    logger.info(f"#dateSpansDiv 10Y not found, available: {success.get('buttons', []) if success else 'N/A'}")

    # ── Step 3: Neither worked — use calendar with 10Y lookback ──────────────────
    return {'clicked': False, 'ten_years_ago': ten_years_ago, 'today_str': today_str}

############################################################################################################
############ Convenience function to run the full scraper from scraper module ##############################

def scrape_chart(url: str = None, 
                 id: str = None,
                 country: str = "united-states",
                 indicator: str = None,
                 start_date: str = None,   #Use "YYYY-MM-DD" format. Only for "mixed" method.
                 end_date: str = None,   #Use "YYYY-MM-DD" format. Only for "mixed" method.
                 method: Literal["path", "tooltips", "mixed", 'highcharts_api'] = "highcharts_api",
                 scraper: TE_Scraper = None,
                 driver: webdriver = None, 
                 use_existing_driver: bool = False,
                 headless: bool = True, 
                 wait_time: int = 5,
                 browser: str = 'firefox') -> TE_Scraper:
    
    """ This convenience function will scrape a chart from Trading Economics and return a TE_Scraper object with the series data in
    the 'series' attribute. Metadata is also retreived and stored in the 'series_metadata' & 'metadata' attributes.
    
    *There are multiple ways to use this function:*

    - Supply URL of the chart to scrape OR supply country + indicator, or just id of the chart to scrape. country and indicator are the latter parts of the 
    full chart URL. e.g for URL: 'https://tradingeconomics.com/united-states/business-confidence', we could instead use country='united-states' 
    and indicator ='business-confidence'. Or use id = "united-states/business-confidence". For US, you can supply just the indicator as the default country is 
    'united-states'.
    - You can leave scraper and driver as None and the function will create a new TE_Scraper object for that URL and use it to scrape the data.
    You can however save time by passing either a scraper object or a driver object to the function. This is still somewhat experimental though 
    and may not work.
    
    **Parameters**

    - url (str): The URL of the chart to scrape.
    - id (str): The id of the chart to scrape. This is the latter part of the URL after the base URL. e.g 'united-states/business-confidence'.
    - country (str): The country of the chart to scrape. Default is 'united-states'.
    - indicator (str): The indicator of the chart to scrape. Default is 'business-confidence'.
    - start_date (str): The start date of the series to scrape. Use "YYYY-MM-DD" format. Only applies to the "mixed" method.
    Default is None. If using None it will get max available date range.
    - end_date (str): The end date of the series to scrape. Use "YYYY-MM-DD" format. Only applies to the "mixed" method. Default is None. 
    If using None it will get max available date range.
    Currently start and end dates only apply when using the 'tooltips' method.
    - method (str): The method to use to scrape the data. Options are 'path', 'tooltips', 'mixed' and 'highcharts_api'. Default is 'highcharts_api'. The 'path' method
    takes the path element of the trace on the svg chart and then later scales series using the y-axis values. 'tooltips' uses the tooltip box on the chart to get the
    whole series data. The 'path' method is likely to work yet could have inacuraccies in values. The 'tooltips' method is more accurate. Try several and 
    decide what works best for you. Update: v0.3.2 added 'highcharts_api' method which uses the Highcharts API to get the series data. This is handsdown the best
    method to use if it works for the chart you are scraping.
    - scraper (TE_Scraper): A TE_Scraper object to use for scraping the data. If this is passed, the function will not create a new one.
    - use_existing_driver (bool): Whether to use the existing webdriver of the scraper object if it exists. Default is False.
    - driver (webdriver): A Selenium WebDriver object to use for scraping the data. If this is passed, the function will not create a new one. If 
    scraper and driver are both passed, the webdriver of the scraper object will be used rather than the supplied webdriver.
    - headless (bool): Whether to run the browser in headless mode (display no window).
    - browser (str): The browser to use, either 'chrome' or 'firefox'. Default is 'firefox'. Only firefox is supported at the moment (v0.3.0).

    **Returns**
    - TE_Scraper object with the scraped data or None if an error occurs.
    """

    if start_date is not None:
        print("WARNING: Trading Economics has disabled the custom date range setter for non-premium users. Data may be limited based on subscription level.")
        # Note: We now try to use MAX button to get the maximum available data
    if end_date is None:
        end_date = datetime.datetime.now().strftime("%Y-%m-%d")
    if scraper is not None:  
        logger.info(f"Using existing scraper object supplied {scraper}.")
        sel = scraper
        # List of attributes to delete if they exist to reset scraper for overwriting.
        attrs_to_delete = ['series', 'series_metadata', 'metadata', 'x_index', 'y_axis', "frequency", "start_end",
                    '_date_span',  '_chart_type',  'last_url',  'series_name', 'date_spans',  'date_span_dict',
                     'latest_points',  'date_series', 'plot']
        # Delete each attribute if it exists
        for attr in attrs_to_delete:
            if hasattr(sel, attr):
                delattr(sel, attr)

        if driver is None:
            driver = scraper.driver
        else:
            scraper.driver = driver
    else:
        sel = TE_Scraper(driver = driver, browser = browser, headless = headless, use_existing_driver=use_existing_driver)

    if url is None:
        if indicator is not None:   #Use country and id to create the URL if URL not supplied.
            url = f"https://tradingeconomics.com/{country}/{indicator}"
        elif indicator is None and id is not None:
            url = f"https://tradingeconomics.com/{id}"
        else:
            print("No URL, id or indicator supplied.")
            logger.debug("No URL, id or indicator supplied.")
            return None
    else:
        pass

    logger.info(f"scrape_chart function: Scraping chart at: {url}, time: {datetime.datetime.now()}, method: {method}")
    if sel.load_page(url, extra_wait_time=wait_time):  # Load the page...
        sel.scrape_metadata()  ## Scrape the metadata for the data series from the page.
    else:
        print("Error loading page at: ", url)
        logger.debug(f"Error loading page at: {url}")
        return None

    if method == "tooltips":
        if not hasattr(sel, "tooltip_scraper"):
            sel.init_tooltipScraper()  ## Initialize the tooltip scraper.
        # Try commodity 10Y button first, then standard #dateSpansDiv, then calendar fallback
        result = _click_10y_button(sel.driver, logger)
        if result is True:
            pass  # 10Y clicked successfully via menu2-bottom or dateSpansDiv
        elif isinstance(result, dict) and not result.get('clicked'):
            sel.custom_date_span_js(start_date=result['ten_years_ago'], end_date=result['today_str'])
            logger.info(f"10Y button not clickable — set date span to 10Y lookback via calendar: {result['ten_years_ago']} to {result['today_str']}")
        else:
            sel.custom_date_span_js(start_date="2010-01-01", end_date="2024-06-01")
            logger.info("10Y button unknown state — falling back to custom_date_span_js")
        try:
            sel.tooltip_scraper.initialize_tooltip_simple()  #Initialize the tooltips on the page by moving mouse onto chart.
        except Exception as e:
            logger.info(f"Error initializing tooltips: {str(e)}")
            return None
        try:
            sel.full_series_fromTooltips()  #Scrape the full series from the tooltips on the chart.
            logger.info("Successfully scraped full series from tooltips.")
        except Exception as e:
            print("Error scraping full series from tooltips: ", str(e))
            logger.info(f"Error scraping full series from tooltips: {str(e)}")
            return None
        
    elif method == "path":
        # Try commodity 10Y button first, then standard #dateSpansDiv, then calendar fallback
        result = _click_10y_button(sel.driver, logger)
        if result is True:
            pass  # 10Y clicked successfully
        elif isinstance(result, dict) and not result.get('clicked'):
            sel.custom_date_span_js(start_date=result['ten_years_ago'], end_date=result['today_str'])
            logger.info(f"10Y button not clickable — set date span to 10Y lookback via calendar: {result['ten_years_ago']} to {result['today_str']}")
        else:
            sel.custom_date_span_js(start_date="2010-01-01", end_date="2024-06-01")
            logger.info("10Y button unknown state — falling back to custom_date_span_js")
        try: #Create the x_index for the series. This is the most complicated bit.
            sel.make_x_index(force_rerun_xlims = True, force_rerun_freqdet = True)  
        except Exception as e:
            print("Error with the x-axis scraping & frequency deterination using Selenium and tooltips:", str(e))
            logger.debug(f"Error with the x-axis scraping & frequency deterination using Selenium and tooltips: {str(e)}")
            return None

        try:  #Scrape the y-axis values from the chart.
            yaxis = sel.get_y_axis(set_global_y_axis=True)
            print("Successfully scraped y-axis values from the chart:", " \n", yaxis) 
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

        print(f"Got metadata. \n\nSeries tail: {sel.series.tail()} \n\nScraping complete! Happy pirating yo!")
        logger.debug(f"Scraping complete, data series retrieved successfully from chart at: {url}")
    
    ## Most accurate method but slowest. Determine start & end dates for full series and frequency, make x-index. Then scrape the data from tooltips
    # using multiple runs of the chart with different date spans to capture all the data.
    elif method == "mixed":
        # Try commodity 10Y button first, then standard #dateSpansDiv, then calendar fallback
        result = _click_10y_button(sel.driver, logger)
        if result is True:
            pass  # 10Y clicked successfully
        elif isinstance(result, dict) and not result.get('clicked'):
            sel.custom_date_span_js(start_date=result['ten_years_ago'], end_date=result['today_str'])
            logger.info(f"10Y button not clickable — set date span to 10Y lookback via calendar: {result['ten_years_ago']} to {result['today_str']}")
        else:
            sel.custom_date_span_js(start_date="2010-01-01", end_date="2024-06-01")
            logger.info("10Y button unknown state — falling back to custom_date_span_js")
        try: #Create the x_index for the series. This is the most complicated bit.
            sel.make_x_index(force_rerun_xlims = True, force_rerun_freqdet = True)  
        except Exception as e:
            logger.info(f"Error with the x-axis scraping & frequency deterination using Selenium and tooltips: {str(e)}")
            return None
        
        if not hasattr(sel, "tooltip_scraper"):
            sel.init_tooltipScraper()  ## Initialize the tooltip scraper.
        try:
            sel.tooltip_scraper.initialize_tooltip_simple()  #Initialize the tooltips on the page by moving mouse onto chart.
        except Exception as e:
            logger.info(f"Error initializing tooltips: {str(e)}")
            return None
        
        try:  
            if sel.tooltip_multiScrape():  ## Scrape the full series from the chart using multiple runs of the javascript tooltip scraper.
                logger.info("Successfully scraped full series using mixed method.")
            else:
                raise Exception("Error scraping full series using mixed method.")
        except Exception as e:
            logger.info(f"Error scraping full series using mixed method: {str(e)}")
            return None
        
    elif method == "highcharts_api":
        # Try the commodity 10Y button first (menu2-bottom), then standard #dateSpansDiv, then calendar fallback
        result = _click_10y_button(sel.driver, logger)
        if result is True:
            pass  # 10Y clicked successfully
        elif isinstance(result, dict) and not result.get('clicked'):
            sel.custom_date_span_js(start_date=result['ten_years_ago'], end_date=result['today_str'])
            logger.info(f"10Y button not clickable — set date span to 10Y lookback via calendar: {result['ten_years_ago']} to {result['today_str']}")
        else:
            sel.custom_date_span_js(start_date="2010-01-01", end_date="2024-06-01")
            logger.info("10Y button unknown state — falling back to custom_date_span_js")
        try:
            # Use new method to scrape series from Highcharts API.
            sel.series_from_highcharts()
            logger.info("Successfully scraped series from Highcharts API.")
        except Exception as e:
            logger.info(f"Error scraping series from Highcharts API: {str(e)}")
            return None

    else:
        logger.info("Invalid method supplied. Use 'path', 'tooltips', 'mixed' or 'highcharts_api'.")
        return
    
    
    return sel #Return the TE_Scraper object with the series data in the 'series' attribute.
