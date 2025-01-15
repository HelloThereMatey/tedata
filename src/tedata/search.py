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
    

######## Search class to search Trading Economics website and extract search results ##############################
class search_TE(object):
    """Class for searching Trading Economics website and extracting search results.
    This class is designed to search the Trading Economics website for a given term and extract the search results.
    It can load the search page, enter a search term, and extract the URLs of the search results.

    **Init Parameters:**

    - driver (webdriver): A Selenium WebDriver object, can put in an active one or make a new one for a new URL.
    - browser (str): The browser to use for scraping, either 'chrome' or 'firefox'.
    - search_term (str): The term to search for on the website.
    - headless (bool): Whether to run the browser in headless mode (show no window).
    """
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
        """Load the Trading Economics home page."""
        # Load page
        try:
            print("Loading home page...")
            self.driver.get("https://tradingeconomics.com/")
        except Exception as e:
            print(f"Error occurred: {str(e)}")

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

        print("Attempting to scrape data for result ", result_num, ", ", self.result_table.loc[result_num, "country"], self.result_table.loc[result_num, "metric"] )
        if hasattr(self, "result_table"):
            url = self.result_table.loc[result_num, "url"]
            print(f"Scraping data from: {url}")
            self.scraped_data = scrape_chart(url, driver = self.driver, headless=self.headless, browser=self.browser)
            return self.scraped_data
        else:
            print("No search results found.")
            return None
        