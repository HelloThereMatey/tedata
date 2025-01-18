# tedata

Download data from Trading Economics without an account or API key. Uses Selenium and BeautifulSoup4 to scrape data directly from charts. Should run on linux, max OSX or windows.

## System Requirements

This package requires a browser that can be automated via selenium. **ONLY FIREFOX BROWSER IS CURRENTLY SUPPORTED**. Ensure that you have the latest stable version of Firefox installed in order to use this package.

- Firefox (version 115.0.0 or higher)
- Python v3.9 or higher.

You can download Firefox from:

- [Firefox](https://www.mozilla.org/firefox/new/)

### Python package requirements:

- pandas
- plotly
- beautifulsoup4
- selenium

These will be automaticaly installed if you use pip to install tedata from pypi.

## Installation

### Install from pypi

```bash
pip install tedata
```

Ensure that you also have firefox browser installed.

## USAGE

prod_tests.ipynb shows how to use the package in detail in a jupyter notebook. Refer to that for the better guide.

### Import tedata

```python
import tedata as ted
```

### Search for indicators and downlad the data

```python
# Intialize new search_TE object which uses selenium.webdriver.
search = ted.search_TE()  # Intialize new search_TE object which uses selenium.
# Use the 'search_trading_economics' method to search the home page using the search bar.
search.search_trading_economics("ISM Manufacturing") 

# View top search results. Results are output as a pandas dataframe.
print(search.result_table.head(3))
```

| result | country | metric | url |
|--------|---------|---------|-----|
| 0 | united states | business confidence | https://tradingeconomics.com/united-states/business-confidence |
| 1 | united states | ism manufacturing new orders | https://tradingeconomics.com/united-states/ism-manufacturing-new-orders |
| 2 | united states | ism manufacturing employment | https://tradingeconomics.com/

Scrape data for second search result. This extracts the time-series from the svg chart displayed on the page at the URL shown. The data will be stored in the "scraped_data" attribute of the search_TE object. The 

```python
search.get_data(1)

# Access the data. The scraped_data attribute is a TE_Scraper object
scraped = search.scraped_data
# The time-series is a pandas series stored in the 
print(scraped.series)

# Plot the series (uses plotly backend). Will give nice interactive chart in a jupyter notebook. 
search.plot_series()


```
