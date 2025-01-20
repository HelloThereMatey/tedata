<style>
    p {font-size: 12px}
    li {font-size: 12px}
    figcaption {font-size: 12px}
    table {font-size: 12px}
</style>

## tedata

Download data from Trading Economics without an account or API key. Uses Selenium and BeautifulSoup4 to scrape data directly from charts. Should run on linux, mac OS or windows.

### System Requirements

This package requires a browser that can be automated via selenium. **ONLY FIREFOX BROWSER IS CURRENTLY SUPPORTED**. Ensure that you have the latest stable version of Firefox installed in order to use this package. We should be able to add support for Chrome soon.

- Firefox (version 115.0.0 or higher)
- Python v3.9 or higher.

You can download Firefox from:

- [Firefox](https://www.mozilla.org/firefox/new/)

#### Python package requirements:

- plotly
- beautifulsoup4
- selenium
- kaleido (for export of plotly fig to image)

These will be automaticaly installed if you use pip to install tedata from pypi.

### Installation

#### Install from pypi

```bash
pip install tedata
```

Ensure that you also have firefox browser installed.

### USAGE

prod_tests.ipynb shows how to use the package in detail in a jupyter notebook. Refer to that for the better guide.

#### Import tedata

```python
import tedata as ted
```

#### Search for indicators and download the data

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
| 0 | united states | business confidence | [https://tradingeconomics.com/united-states/business-confidence](https://tradingeconomics.com/united-states/business-confidence) |
| 1 | united states | ism manufacturing new orders | [https://tradingeconomics.com/united-states/ism-manufacturing-new-orders](https://tradingeconomics.com/united-states/ism-manufacturing-new-orders) |
| 2 | united states | ism manufacturing employment | [https://tradingeconomics.com/](https://tradingeconomics.com/) |

Scrape data for the second search result using the "get_data"method of the search_TE class. This extracts the time-series from the svg chart displayed on the page at the URL. The data is stored in the "scraped_data" attribute of the search_TE object as a "TE_Scraper" object.

```python
search.get_data(1)

# Access the data. The scraped_data attribute is a TE_Scraper object
scraped = search.scraped_data
# The time-series is a pandas series stored in the "series" attribute.
print(scraped.series)

# Plot the series (uses plotly backend). Will make a nice interactive chart in a jupyter notebook. 
scraped.plot_series()

#Export the plot as a static png image. You can use format = "html" to export an interactive chart.

scraped.save_plot(format="png")
```
![Static plot](docs/ISM_Manufacturing.png)

[Interactive plot](https://github.com/HelloThereMatey/tedata/blob/main/docs/ISM_Manufacturing.html)

<!-- # For GitHub Pages setup (in repo root)
#[View Interactive Plot](https://username.github.io/tedata/example_plot.html) -->

Metadata for the series is stored in the "metadata" attribte of the TE_Scraper object as a dict and as a pd.Series in the "series_metadata" attribute.

```python
print(scraped.metadata)
```

{'units': 'points',
 'original_source': 'Institute for Supply Management',
 'title': 'United States ISM Manufacturing New Orders',
 'indicator': 'ism manufacturing new orders',
 'country': 'united states',
 'length': 900,
 'frequency': 'MS',
 'source': 'Trading Economics',
 'id': 'united-states/ism-manufacturing-new-orders',
 'start_date': '1950-01-01',
 'end_date': '2024-12-01',
 'min_value': 24.200000000000998,
 'max_value': 82.6000000000004,
 'description': "The Manufacturing ISM Report On Business is based... ...is generally declining."}


