from typing import Literal
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from bs4 import BeautifulSoup
import time
import weakref
import gc

import logging
# Get the logger from the parent package
logger = logging.getLogger('tedata.base')

# Base standalone functions. ##############################################################
def find_active_drivers(close_all_drivers: bool = False, close__all_scrapers: bool = False) -> dict:
    """Find all active selenium webdriver instances in memory sorted by age.
    
    Args:
        quit_all (bool): If True, quit all found drivers and clear references
        close_scrapers (bool): If True, also find and close any TE_Scraper objects
        
    Returns:
        list: List of tuples (driver, age_in_seconds) sorted by age, excluding weakproxies
    """
    active_drivers = []
    active_scrapers = []
    current_time = time.time()
    
    # Find all webdriver instances and TE_Scraper objects
    for obj in gc.get_objects():
        try:
            # Check for driver instances
            if isinstance(obj, (TimestampedFirefox, TimestampedChrome)) and not isinstance(obj, weakref.ProxyType):
                creation_time = getattr(obj, 'created_at', current_time)
                age = current_time - creation_time
                active_drivers.append((obj, age))
                
            # Check for TE_Scraper objects if requested
            elif obj.__class__.__name__ == 'TE_Scraper':
                active_scrapers.append(obj)
                
        except ReferenceError:
            continue
    
    # Sort by age (second element of tuple)
    active_drivers.sort(key=lambda x: x[1])
    
    # Close TE_Scraper instances if requested
    if close__all_scrapers and active_scrapers:
        logger.info(f"Closing {len(active_scrapers)} active TE_Scraper instances...")
        for scraper in active_scrapers:
            try:
                logger.info(f"Closing TE_Scraper instance")
                scraper.close()
                # Note: We don't delete the reference here to avoid potential issues
                # with the garbage collector while iterating
            except Exception as e:
                logger.isEnabledFor(f"Error closing TE_Scraper: {str(e)}")
        active_scrapers = []
    
    # Quit webdriver instances if requested
    if close_all_drivers and active_drivers:
        logger.info(f"Quitting {len(active_drivers)} active webdriver instances...")
        for driver, age in active_drivers:
            try:
                logger.info(f"Quitting driver (age: {age:.1f}s)")
                driver.quit()  # Close the browser
                del driver    # Remove the reference
            except Exception as e:
                logger.info(f"Error quitting driver: {str(e)}")
        
        # Force garbage collection
        gc.collect()
        active_drivers = []  # Clear the list since all drivers are quit
                
    return {"Active webdrivers": active_drivers, "Active TE_Scrapers": active_scrapers}


##### Base Webdriver classes ##############################################################
class TimestampedFirefox(webdriver.Firefox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.created_at = time.time()

class TimestampedChrome(webdriver.Chrome):   #Chrome can work for other things but it's not working for scraping Trading Economics charts at the moment....
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.created_at = time.time()

class Generic_Webdriver:
    """Generic webdriver class for initializing a Selenium WebDriver. This is the base class for the TE_Scraper and TooltipScraper classes.
    It can be used to create a new webdriver or use an existing one. The browser type can be set to 'chrome' or 'firefox'.
    It holds a wedbdriver object and a WebDriverWait object as components and has attributes that help keep track of things.
    
    **Init Parameters:**
    - driver (webdriver): If provided, the class will use this webdriver instance instead of creating a new one.
    - browser (str): The browser to use for the webdriver. Options are 'chrome' or 'firefox'.
    - headless (bool): If True, the browser will run in headless mode.
    - use_existing_driver (bool): If True, the class will attempt to use an existing 'spare' webdriver instance if one is found."""

    # Define browser type with allowed values
    BrowserType = Literal["chrome", "firefox"]
    def __init__(self, 
                driver: webdriver = None, 
                browser: BrowserType = "firefox", 
                headless: bool = True,
                use_existing_driver: bool = False):
        
        self.browser = browser
        self.headless = headless

        active = find_active_drivers() 
        if len(active["Active webdrivers"]) <= 1:
            use_existing_driver = False

        if driver is None and not use_existing_driver:
            if browser == "chrome":
                print("Chrome browser not supported yet. Please use Firefox.")
                logger.debug(f"Chrome browser not supported yet. Please use Firefox.")
                return None
            elif browser == "firefox":
                options = webdriver.FirefoxOptions()
                if headless:
                    options.add_argument('--headless')
                self.driver = TimestampedFirefox(options=options)
            else:
                logger.debug(f"Error: Unsupported browser! Use 'chrome' or 'firefox'.")
                raise ValueError("Unsupported browser! Use 'chrome' or 'firefox'.")
            logger.info(f"New {browser} webdriver created.")
        elif use_existing_driver:   ## May want to change this later to make sure a scraper doesn't steal the driver from a search object.
            self.driver = active["Active webdrivers"][-1][0]
            logger.debug(f"Using existing {browser} driver.")
        else:
            self.driver = driver
            logger.debug(f"Using supplied driver.")
        
        self.wait = WebDriverWait(self.driver, timeout=10)
        self.created_at = time.time()
        self.driver.created_at = self.created_at

## Shared state class ######################################################################
class SharedWebDriverState:
    """Maintain shared state for classes that use the same webdriver.
    This could be used as a mixin class or used via composition as an attribute shared by multiple classes.
    This is used to share the webdriver state between the TE_Scraper and TooltipScraper classes.
    """

    def __init__(self):
        """ Initialize shared state attributes, it is chart_type and date_span which we want to keep synced between the classes."""
        self._date_span = None
        self._chart_type = None
        self._page_source = None
        self._page_soup = None
        self._chart_soup = None
        self._full_chart = None
        self.observers = []

    def register(self, observer):
        self.observers.append(observer)

    @property
    def page_source(self):
        return self._page_source
    @page_source.setter
    def page_source(self, value):
        self._page_source = value
        self._notify_observers('page_source', value)
        # Auto-update soups when source changes
        self._update_soups()

    @property
    def page_soup(self):
        return self._page_soup
    @page_soup.setter
    def page_soup(self, value):
        self._page_soup = value
        self._notify_observers('page_soup', value)

    @property
    def chart_soup(self):
        return self._chart_soup
    @chart_soup.setter
    def chart_soup(self, value):
        self._chart_soup = value
        self._notify_observers('chart_soup', value)

    @property
    def full_chart(self):
        return self._full_chart
    @full_chart.setter
    def full_chart(self, value):
        self._full_chart = value
        self._notify_observers('full_chart', value)

    @property
    def date_span(self):
        return self._date_span
    @date_span.setter
    def date_span(self, value):
        self._date_span = value
        self._notify_observers('date_span', value)

    @property
    def chart_type(self):
        return self._chart_type
    @chart_type.setter
    def chart_type(self, value):
        self._chart_type = value
        self._notify_observers('chart_type', value)

    def _notify_observers(self, attr, value):
        for observer in self.observers:
            setattr(observer, f"_{attr}", value)

    def _update_soups(self):
        """Update BeautifulSoup objects when page source changes"""
        if self._page_source:
            self._page_soup = BeautifulSoup(self._page_source, 'html.parser')
            self._chart_soup = self._page_soup.select_one("#chart")
            self._full_chart = self._chart_soup.contents if self._chart_soup else None
            self._notify_observers('page_soup', self._page_soup)
            self._notify_observers('chart_soup', self._chart_soup)
            self._notify_observers('full_chart', self._full_chart)

### More utility functions ##############################################################

def setup_chrome_driver(headless: bool = True):  #Been trying to get it running with Chrome as well but having issues still......
    chrome_options = webdriver.ChromeOptions()
    if headless:
        chrome_options.add_argument("--headless")
    # Disable notifications
    chrome_options.add_argument("--disable-notifications")
    # Additional preference to block notifications
    prefs = {
        "profile.default_content_setting_values.notifications": 2,
        "profile.default_content_settings.popups": 0
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    # Initialize driver with options
    driver = TimestampedChrome(options=chrome_options)
    return driver