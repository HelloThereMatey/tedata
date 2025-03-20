from bs4 import BeautifulSoup
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
from .base import Generic_Webdriver
from .scrape_chart import scrape_chart

import logging
# Get the logger from the parent package
logger = logging.getLogger('tedata.search')

######## Search class to search Trading Economics website and extract search results ##############################
class search_TE(Generic_Webdriver):
    """Class for searching Trading Economics website and extracting search results.
    This class is designed to search the Trading Economics website for a given term and extract the search results.
    It can load the search page, enter a search term, and extract the URLs of the search results.

    **Init Parameters:**

    - load_homepage (bool): If True, the class will load the Trading Economics home page when initialized.
    - **kwargs: Additional keyword arguments to pass to the Generic_Webdriver class. These are the same as the Generic_Webdriver class.
    These are:
        - browser (str): The browser to use for the webdriver. Options are 'chrome' or 'firefox'.
        - headless (bool): If True, the browser will run in headless mode.
        - use_existing_driver (bool): If True, the class will attempt to use an existing 'spare' webdriver instance if one is found.
        - driver (webdriver): If provided, the class will use this webdriver instance instead of creating a new one.

    """

    def __init__(self,
                load_homepage: bool = True,
                **kwargs):
        
        super().__init__(**kwargs)

        logger.debug(f"Initializing search object with parameters: {kwargs}")

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

            # Check if search box exists
            search_box = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.ID, "thisIstheSearchBoxIdTag")))
            if search_box:
                logger.info("Home page at https://tradingeconomics.com loaded successfully! Search box element found.")
            else:
                logger.info("Home page at https://tradingeconomics.com loaded successfully! Search box element not found though.")
            return search_box
            
        except Exception as e:
            logger.info(f"Error occurred, check internet connection. Error details: {str(e)}")
            logger.debug(f"Error occurred, check internet connection. Error details: {str(e)}")
            return None

    def search_trading_economics(self, search_term: str = None, wait_time: int = 5):
        """Search Trading Economics website for a given term and extract URLs of search results.
        This method will search the Trading Economics website for a given term and extract the URLs of the search results.
        It will enter the search term in the search box, submit the search, and extract the URLs of the search results.
        Results are assigned to the 'results' attribute as a list of URLs and as result_table attribute as a pandas df.

        **Parameters:**

        - search_term (str): The term to search for on the website.
        - wait_time (int): The time to wait for the search results to load, in seconds (if you get an empty table 
        of results, increase this time).
        """

        # Load home page, can't yet figure ourt how to work the search bar from other pages
        if self.driver.current_url != "https://tradingeconomics.com/":
            search_box = self.home_page()
            time.sleep(1)
        else:
            search_box = WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.ID, "thisIstheSearchBoxIdTag")))
 
        if search_term is None:
            search_term = self.search_term
        else:
            self.search_term = search_term
        logger.debug(f"Searching Trading Economics for: {self.search_term}")
        
        try:
        # Wait for search box - using the ID from the HTML
            # Click search box
            logger.info("Clicking search box...")
            search_box.click()
            
            # Enter search term
            logger.info(f"Entering search term: {search_term}")
            search_box.send_keys(search_term)
            time.sleep(0.5)  # Small delay to let suggestions appear
            
            # Press Enter
            logger.info(f"Submitting search, waiting {wait_time}s for page to load...")
            search_box.send_keys(Keys.RETURN)
            
            # Wait a moment to see results  
            ## Need to figure a better way to figure when the search results are loaded...
            results = WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".list-group-item")))
            time.sleep(wait_time)

            self.results = self.extract_search_results(self.driver.page_source)
            self.results_table()
            logger.debug(f"Search for {self.search_term} completed successfully.")
        
        except Exception as e:
            logger.info(f"Error occurred: {str(e)}")
            logger.debug(f"Error on search occurred: {str(e)}")
            return None
        
    def extract_search_results(self, html_content):
        """Extract URLs from search results page"""
        
        results_container = WebDriverWait(self.driver, 30).until(
            EC.all_of(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".list-group")),
                #EC.visibility_of_element_located((By.CSS_SELECTOR, ".list-group")),
            )
        )
        
        print("Found search results on page.")
        time.sleep(1)
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
        
    def get_data(self, result_num: int = 0, method: str = "highcharts_api", start_date: str = None, end_date: str = None):
        """Scrape data for a given search result number.
        This method will scrape data for a given search result number from the search results table.
        It will extract the URL for the result and scrape the data from the chart at that URL.
        The scraped data is assigned to the 'scraped_data' attribute as a TE_scraper object.
        This will use the TE_Scraper class and methods to scrape the data from the Trading Economics website.
        
        **Parameters:**
        - result_num (int): The index of the search result in your result table to scrape the data for.
        - method (str): The method to use for scraping the data. Options are "path" (default) or "tooltips" or "mixed".

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
            self.scraped_data = scrape_chart(url, driver=self.driver, headless=self.headless, browser=self.browser, method=method, start_date=start_date, end_date=end_date)
            if self.scraped_data is not None:
                print(f"Data scraped successfully from: {url}")
                logger.debug(f"Data scraped successfully from: {url}")
            return self.scraped_data
        else:
            print("No search result found with the number specified: ", result_num)
            logger.debug(f"No search result found with the number specified: {result_num}")
            return None
        