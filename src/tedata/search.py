from typing import Literal
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
import time
import pandas as pd
import os

##### Get the directory where this file is housed ########################
wd = os.path.dirname(__file__)
fdel= os.path.sep

## Import the TE_Scraper class from the scraper module ################
from .scraper import scrape_chart
from . import utils
from . import logger

# Create module-specific logger
logger = logger.getChild('search')

######## Search class to search Trading Economics website and extract search results ##############################
class search_TE(object):
    """Class for searching Trading Economics website and extracting search results.
    This class is designed to search the Trading Economics website for a given term and extract the search results.
    It can load the search page, enter a search term, and extract the URLs of the search results.

    **Init Parameters:**

    - driver (webdriver): A Selenium WebDriver object, can put in an active one or make a new one for a new URL.
    - use_existing_driver (bool): Whether to use an existing driver or make a new one.
    - browser (str): The browser to use for scraping, either 'chrome' or 'firefox'.
    - search_term (str): The term to search for on the website. Optional, can also provide it in the search_trading_economics method.
    - headless (bool): Whether to run the browser in headless mode (show no window).
    """
    # Define browser type with allowed values
    BrowserType = Literal["chrome", "firefox"]
    
    def __init__(self, driver: webdriver = None, 
                 use_existing_driver: bool = False,
                 browser: BrowserType = "firefox", 
                 search_term: str = "US ISM Services PMI",
                 headless: bool = True,
                 load_homepage: bool = True):
        
        self.browser = browser
        self.headless = headless

        logger.debug(f"Initializing search object with browser: {browser}, headless: {headless}, use_existing_driver: {use_existing_driver}")
        active = utils.find_active_drivers() 
        if len(active) <= 1:
            use_existing_driver = False

        if driver is None and not use_existing_driver:
            if browser == "chrome":
                print("Chrome browser not supported yet. Please use Firefox.")
                # self.driver = utils.setup_chrome_driver(headless = headless)
            elif browser == "firefox":
                options = webdriver.FirefoxOptions()
                if headless:
                    options.add_argument('--headless')
                self.driver = utils.TimestampedFirefox(options=options)
            else:
                logger.debug(f"Error on driver initialization: Unsupported browser: {browser}")
                raise ValueError("Unsupported browser! Use 'chrome' or 'firefox'.")
            logger.debug(f"New webdriver object initialized: {self.driver}")
            logger.info(f"New webdriver object initialized: {self.driver}")
        elif use_existing_driver:   ## May want to change this later to make sure a scraper doesn't steal the driver from a search object.
            self.driver = active[-1][0]
            logger.debug(f"Using existing webdriver object: {self.driver}")
            logger.info(f"Using existing webdriver object: {self.driver}")
        else:
            self.driver = driver
            logger.debug(f"Using provided webdriver object: {self.driver}")
            logger.info(f"Using provided webdriver object: {self.driver}")
        
        self.wait = WebDriverWait(self.driver, timeout=10)
        logger.debug(f"Driver of search_TE object initialized: {self.driver}")
        self.search_term = search_term
        if load_homepage:
            self.home_page()

    def home_page(self, timeout: int = 30):
        """Load the Trading Economics home page.
        :Parameters:
        - timeout (int): The maximum time to wait for the page to load, in seconds.

        """
        # Load page
        try:
            logger.info("Loading home page at https://tradingeconomics.com/ ...")
            self.driver.get("https://tradingeconomics.com/")

            # Wait for 5 seconds
            time.sleep(5)
            # Check if search box exists
            search_box = self.driver.find_elements(By.ID, "thisIstheSearchBoxIdTag")
            if search_box:
                logger.info("Home page at https://tradingeconomics.com loaded successfully! Search box element found.")
            else:
                logger.info("Home page at https://tradingeconomics.com loaded successfully! Search box element not found though.")
            
        except Exception as e:
            logger.info(f"Error occurred, check internet connection. Error details: {str(e)}")
            logger.debug(f"Error occurred, check internet connection. Error details: {str(e)}")

    def search_trading_economics(self, search_term: str = None):
        """Search Trading Economics website for a given term and extract URLs of search results.
        This method will search the Trading Economics website for a given term and extract the URLs of the search results.
        It will enter the search term in the search box, submit the search, and extract the URLs of the search results.
        Results are assigned to the 'results' attribute as a list of URLs and as result_table attribute as a pandas df.

        **Parameters:**

        - search_term (str): The term to search for on the website.
        """

        self.current_page = self.driver.current_url
        if self.current_page != "https://tradingeconomics.com/":
            self.home_page()
            time.sleep(2)
 
        if search_term is None:
            search_term = self.search_term
        else:
            self.search_term = search_term
        logger.debug(f"Searching Trading Economics for: {self.search_term}")
        
        try:
        # Wait for search box - using the ID from the HTML
            search_box = WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.ID, "thisIstheSearchBoxIdTag")))
   
            # Click search box
            logger.info("Clicking search box...")
            search_box.click()
            
            # Enter search term
            logger.info(f"Entering search term: {search_term}")
            search_box.send_keys(search_term)
            time.sleep(1)  # Small delay to let suggestions appear
            
            # Press Enter
            logger.info("Submitting search...")
            search_box.send_keys(Keys.RETURN)
            
            # Wait a moment to see results
            time.sleep(3)

            self.results = self.extract_search_results(self.driver.page_source)
            self.results_table()
            logger.debug(f"Search for {self.search_term} completed successfully.")
        
        except Exception as e:
            logger.info(f"Error occurred: {str(e)}")
            logger.debug(f"Error on search occurred: {str(e)}")
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
        """Create a DataFrame from the search results"""

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
        """Scrape data for a given search result number.
        This method will scrape data for a given search result number from the search results table.
        It will extract the URL for the result and scrape the data from the chart at that URL.
        The scraped data is assigned to the 'scraped_data' attribute as a TE_scraper object.
        This will use the TE_Scraper class and methods to scrape the data from the Trading Economics website.
        
        **Parameters:**
        - result_num (int): The index of the search result in your result table to scrape the data for.

        **Returns:**
        - scraped_data (TE_Scraper): The scraped data object. The data can be accessed from the 'series' attribute of the TE_SCraper object
        that is returned. This object is also saved as the "scraped_data" attribute of the search_TE object.  The maximum length 
        for the indicator is always retrieved. Use slicing to reduce length if needed.

        ** Example: **
        - Run a search and display the "result_table" attribute of the search_TE object to see the search results:

        ```
        search = search_TE()
        search.search_trading_economics("US ISM Services PMI")
        search.result_table
        ````

        - Scrape the data for the 11th search result (counts from 0):
        
        ```
        scraped = search.get_data(10)
        scraped.plot_series()  # This will plot an interactive plotly chart of the series.
        ```

        """

        print("Attempting to scrape data for result ", result_num, ", ", self.result_table.loc[result_num, "country"], self.result_table.loc[result_num, "metric"])
        logger.debug(f"Attempting to scrape data for result {result_num}, {self.result_table.loc[result_num, 'country']} {self.result_table.loc[result_num, 'metric']}")
        if hasattr(self, "result_table"):
            url = self.result_table.loc[result_num, "url"]
            print(f"Scraping data from: {url}")
            self.scraped_data = scrape_chart(url, driver = self.driver, headless=self.headless, browser=self.browser)
            if self.scraped_data is not None:
                print(f"Data scraped successfully from: {url}")
                logger.debug(f"Data scraped successfully from: {url}")
            return self.scraped_data
        else:
            print("No search result found with the number specified: ", result_num)
            logger.debug(f"No search result found with the number specified: {result_num}")
            return None
        