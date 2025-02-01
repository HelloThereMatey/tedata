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
There are several different ways to use tedata to get data from trading economics:

1. Use the `search_TE` class from the search module to search for data and then download it.
2. Use the trading economics website to locate the data you wish to get. Copy the URL or just country and indicator names for it. Download the data using the `scrape_chart` convenience function from scraper module using the URL or country + indicator names.
3. Use the command line to download data directly to an .xlsx file using a URL.
4. Run manually the steps that are performed by the `scrape_chart` function.

#### #1: Search for indicators and download data

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

Scrape data for the second search result using the "get_data"method of the search_TE class. This extracts the time-series from the svg chart displayed on the page at the URL. The data is stored in the "scraped_data" attribute of the search_TE object as a "TE_Scraper" object. Data download should take ~20s or so for a reasonable internet connection speed (> 50 Mbps).

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

Metadata for the series is stored in the "metadata" attribte of the TE_Scraper object as a dict and as a pd.Series in the "series_metadata" attribute.

```python
print(scraped.metadata)

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
 ```

#### #2: Single line data download

There is a convenience function "scrape_chart"in the scraper module that will run the series of steps needed to download the data for an indicator from Trading Economics. This can be performed with a single line in a jupyter notebook or similar.

```python
#This returns a TE_scraper object with teh data stored in the "series" attribute.
scraped = ted.scrape_chart(URL = "https://tradingeconomics.com/united-states/ism-manufacturing-new-orders")

# Metadata is stored in the "metadata" attribute and the series is easily plotted 
# using the "plot_series" method. 
```

You can then plot your data and export the plot using the "plot_series" and "save_plot" methods as shown above. Export your data using pandas or native python e.g:

```python
# Create Excel writer
with pd.ExcelWriter(filepath) as writer:
    # Save series data
    scraped.series.to_excel(writer, sheet_name='Data')
    # Save metadata
    scraped.series_metadata.to_excel(writer, sheet_name='Metadata')
```

#### #3 Use command line

You can run the `scrape_chart` function from command line. Invoking the package in command line will run the functionality in the _main_ module. Only a URL can be used to indicate the data to download. This will save your data and metadata to an excel (.xlsx) file in the current working directory.

```bash
python -m tedata https://tradingeconomics.com/united-states/ism-manufacturing-new-orders
```

#### #4: Run through the steps in Jupyter or similar

Running steps individually can have an advantage in terms of download speed as you can avoid initializing new webdrivers and other objects with every new dataset download.

```python
scr = ted.TE_Scraper(use_existing_driver=True)  ## Initialize a new TE_scraper object.

scr.load_page("https://tradingeconomics.com/united-states/corporate-profits")
scr.click_button(scr.find_max_button())  ## Click the button on chart to set date range to max.
scr.get_y_axis()   ## Get the y-axis tick positions (pixel co-ordinates) and values.
scr.get_element() ## Get the element containing the chart.
scr.series_from_element() ## Get the series from the element, this is the data trace on the chart from the path attribute of the svg chart.

```

```python
scr.make_x_index(force_rerun=True)  ## Make the x-axis index from the chart. This scrapes some points from tooltips using selenium.
scr.scale_series() ## Scale the series to the y-axis values to convert the pixel co-ordinates to actual data values.
```

```python
scr.scrape_metadata() ## Scrape the metadata for the data series from the page.
scr.plot_series() ## Plot the series.
```

You can then use the same TE_Scraper object to download other datasets, overwriting the previous data series and metadata. You'd probably want to export the data first.
Overwriting the data in the object will be faster than creating a new TE_Scraper. Use the `scrape_chart` function and provide your scraper object:

```python
scrape_chart(scraper = scr, id = "gdp", country: str = "united-states")
```

### Additional Notes

- If using a headless webdriver instance, i.e a browser window is shown, DO NOT CHANGE ANY SETTINGS ON THE CHART MANUALLY.
- Specifically changing the chart_type cannot be detected as the code stands now. This could then lead to scraping failures.
- Best to run in headless mode or if running with head, only use the browser window for viewing the actions as they are taken by the webdriver.

### Reporting issues and debugging

The package has extensive logging which should help me identify where things went wrong if you encounter a problem. Please log an issue or pull request and send me your logfile if you run into a problem. logfiles are stored in `/src/tedata/logs`.
