## tedata

Download data from Trading Economics without an account or API key. Trading Economics API costs upwards of $100 USD per month for data access. Using this you will be able to download a large part of the data available on the site for free. Trading Economics has one of the greatest repositories of macroeconomic data on Earth. Download data series into a Jupyter notebook environment or save series directly to an excel file (.xlsx) using command line. This utilizes Selenium and BeautifulSoup4 to scrape data from charts. Runs fine on linux, mac OS or windows.

**Update 2025-08-19:** It appears that Trading Economics have vastly upgraded their anti-scraping measures. The maximum length of data that can be downloaded using tedata is now limited to 10 years. Most series on the site can be downloaded but the historical length is now limited.

Note that the current version (v0.3.x) only supports scraping of data from the economic data type of chart (example below). The more interactive type chart (second example chart image below) that displays higher frequency data for stocks, commodities etc is not yet working for data download.

![Static plot](docs/te_chart.PNG)

**Above:** You can download the data from charts that look like this. The highest frequency data I've seen on these is weekly. I suspect weekly is the highest data frequency accessible via tedata at the moment.

![Static plot](docs/te_chart2.PNG)

**Above:** You cannot yet download the high frequency data from these types of chart. I'm sure we'll figure out how to do it soon though...

### System Requirements

This package requires a browser that can be automated via selenium. **ONLY FIREFOX BROWSER IS CURRENTLY SUPPORTED**. Ensure that you have the latest stable version of Firefox installed in order to use this package. We should be able to add support for Chrome soon.

- Firefox (version 115.0.0 or higher)
- Python v3.9 or higher.

You can download firefox from: [firefox](https://www.mozilla.org/firefox/new/)

#### Python requirements:

- plotly
- beautifulsoup4
- selenium
- pandas
- kaleido (optional, for export of plotly fig to image).
- openpyxl (optional, for export of pandas datastructures to excel).
- nbformat (optional, for interactive plotly charts in jupyter notebooks).

These will be automaticaly installed if you use pip to install tedata.

### Installation

#### Install from pypi

Install from PyPi. Has been published to PyPi as of v0.3.5. Use the command below:
```bash
pip install tedata
```

Ensure that you also have firefox browser installed.

### USAGE

**NOTE:** "tedata_walkthrough.ipynb" in the "tests" directory has detailed usage instructions & examples in a jupyter notebook. Refer to that for the best available usage guide.

#### Import tedata

```python
import tedata as ted
```
**Note:** On windows, if you get a permission denied error related to logging, such as:
```python
PermissionError: [Errno 13] Permission denied: 'c:\ProgramData\miniconda3\envs\ted\Lib\site-packages\tedata\logs\tedata.log
```
You need to run the package as administrator. Run VSCode or shell as admin. Alternatively you can disable logging by importing like this:
```python
import os
os.environ['TEDATA_DISABLE_LOGGING'] = 'true'
import tedata  as ted # No logging output will appear
```
However, without logging there will be no messages printed to console and it may be hard to figure out what went wrong if an error occurs.

#### There are several different ways to use tedata to get data from trading economics

##### Inside a Jupyter Notebook, python shell or script:

**1.** Use the `search_TE` class from the search module to search for data and then download it.
**2.** Use the trading economics website to locate the data you wish to get. Copy the URL or just the country and indicator names (latter part of URL). Download the data using the `scrape_chart` convenience function (in scraper module) with the URL or country + indicator names.
**3.** Run manually the steps that are performed by the `scrape_chart` function.

##### Using command line

**4.** Use a shell such as bash CLI to download data directly, saving it to an .xlsx file in the current wd. Use --help or -h to bring up information:

```python
python -m tedata -h

usage: __main__.py [-h] [--head] [--method {path,tooltips,mixed}] url

positional arguments:
  url                   URL of Trading Economics chart to scrape
options:
  -h, --help            show this help message and exit
  --head, -he           Run browser with head i.e show the browser window. Default is headless/hidden window.
  --method, -m          Scraping method to use either: "path", "tooltips", "mixed" or "highcharts_api". 
                        If not specified, default method "path" will be used.
```

Specify a URL to a Trading Economics chart as the command argument. Example below will get data for "ism-manufacturing-new-orders" series for country = "united-states". The flag --head will set the webdriver to not run in headless mode (headless is the default). Omit --head to run headless.
```bash
python -m tedata --head --method mixed "https://tradingeconomics.com/united-states/ism-manufacturing-new-orders"
```

Having a head will bring up browser (firefox) window. Watch as the scraper does it's thing. It'll take between 15 - 40 s. So head may be more entertaining than waiting without head. Once complete, a window will open in your browser to display the interactive plotly chart with your data. Data is saved to .xlsx at the same time.

Here the method "mixed" was used with a non-headless browser instance as it is more entertaining. The "highcharts_api" method is default though and is generally the best method to use. Omit method specification in order to use the default.

### Using Jupyter Notebook or Similar

This is the recommended way to use the package. You will also save time on individual data downloads relative to using the CLI.

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

Scrape data for the second search result using the ```get_data``` method of the search_TE class. This extracts the time-series from the svg chart displayed on the page at the URL. The data is stored in the "scraped_data" attribute of the search_TE object as a "TE_Scraper" object. Data download should take 15 - 30s for a reasonable internet connection speed (> 8 Mbps), using "path" method.

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
 'description': "The Manufacturing ISM Report On Business is based..."}
 ```

#### #2: Download data in a Single line using ```scrape_chart()```

There is a convenience function "scrape_chart" that will run the series of steps needed to download the data for an indicator from Trading Economics. This can be performed with a single line in a jupyter notebook or similar.

```python
#This returns a TE_scraper object with the data stored in the "series" attribute.
scraped = ted.scrape_chart(URL = "https://tradingeconomics.com/united-states/ism-manufacturing-new-orders")

# Metadata is stored in the "metadata" attribute and the series is easily plotted 
# using the "plot_series" method. 
```

You can then plot your data and export the plot using the "plot_series" and "save_plot" methods as shown above. You can then export your data and save to excel (.xlsx) using the ```export_data``` method. Data and Metadata will be saved to sheets in the file with those names. The file_name will be like:
 ```f"{country}_{indicator}.xlsx"```
```python
scraped.export_data(filename = "my_data") #Will save to current wd as "my_data.xlsx"
```

Alternatively, export to .csv or .hd5 (my favourite) using pandas e.g:

```python

scraped.series.to_csv("my_data_series.csv", sheet_name='Data')
# Save metadata
scraped.series_metadata.to_csv("my_series_metadata.csv", sheet_name='Metadata')

# Store to .hd5 which is a dict like object great for pandas data with optimized save speed & file size.
with pd.HDFStore(f"{country}_{indicator}.hd5") as store:
    store.put('Data', scraped.series)
    store.put('Metadata', scraped.series_metadata)
# Load the data later using
series = pd.read_hdf(f"{country}_{indicator}.hd5", key = "Data")
metadata = pd.read_hdf(f"{country}_{indicator}.hd5", key = "Metadata")
```

##### DIFFERENT SCRAPING METHODS

```scrape_chart()```has the keyword argument 'method' with the possible values of "path", "tooltips", "mixed" or "highcharts_api". Default is "highcharts_api".

- The "path" method takes the path element for the data series trace from the svg chart. It then scales the pixel co-ordinates using the Y-axis values
- "tooltips" takes the data values frm the tooltips which show up as the cursor is dragged across the chart. This method may end up with holes in your data if there are many datapoints in the series.
- "mixed" uses a combination of the two approaches and scrapes all of the data-points from the tooltips in multiple runs. This method should yield the highest accuracy.
- "highcharts api" takes the series data directly from the highcharts api active on the page. This method was discovered for v0.3.3 and is the fastest and most accurate. If this method works for the series you are trying to get, it should always be used. This has been made the default from v0.3.3.

If the "highcharts api" method does not work for you give the other methods a try. These other methods may also work on other sites that do not have the highcharts api active.

![Static plot](docs/aus_biz_conf.PNG)
**Above:** Chart with data from the 3 scraping methods (excepting 'highcharts_api') displayed. You can see how the path method yields slightly different data, while mixed & tooltips have yielded an identical series for this example. The tooltips trace cannot be seen as it is under the mixed trace.

#### #3: Run through the steps individually

Running steps individually can have an advantage in terms of download speed as you may be able to avoid initializing new webdrivers with every new dataset download. Below we will download data for US corporate profits using the 'path'method.

```python
scr = ted.TE_Scraper(use_existing_driver=True)  ## Initialize a new TE_scraper object.
scr.load_page("https://tradingeconomics.com/united-states/corporate-profits"):  # Load the page containing the chart you want to scrape.
```

I've put the steps into separate code cells based upon the time each will take. Making the x-index below is the slow step and ~80% of the time needed to scrape the data is this step.
```python
scr.make_x_index(force_rerun_xlims = True, force_rerun_freqdet = True)  
```
It uses selenium to get data from the tooltips for the first date & last 5 or so dates for the series. From this, frequency can be detrmined & datetime index generated.

```python
scr.get_y_axis(set_global_y_axis=True) ## Get the y-axis tick positions (pixel co-ordinates) and values.
scr.series_from_chart_soup(set_max_datespan=True)  #Get the series data from path element that is the series trace on the svg chart.
scr.apply_x_index()  ## Apply the x_index to the series, this will resample the data to the frequency of the x_index.
scr.scale_series()  ## Scale the series to the y-axis values to convert the pixel co-ordinates to actual data values.
```

```python
scr.scrape_metadata() ## Scrape the metadata for the data series from the page.
scr.plot_series() ## Plot the series.
```

You can then use the same TE_Scraper object to download other datasets, overwriting the previous data series and metadata. You'd probably want to export the previous data first. Overwriting will be faster than creating a new ```TE_Scraper```. Note that this does not always work. Use the `scrape_chart` function and provide your scraper object as a keyword argument. This will get data for US GDP:

```python
scrape_chart(scraper = scr, id = "gdp", country = "united-states")
```

### Additional Notes

- If not using a headless webdriver instance, i.e a browser window is shown, DO NOT CHANGE ANY SETTINGS ON THE CHART MANUALLY.
- Specifically, changing the chart_type (e.g line chart to bar) cannot be detected as the code stands now (v0.3.x). This could then lead to scraping failures.
- Best to run in headless mode or if running with head, only use the browser window for viewing the actions as they are taken by the webdriver.

### Reporting issues and debugging

The package has extensive logging which should help me identify where things went wrong if you encounter a problem. Please not that there are fleeting errors that can occur with webscraping based approaches and you should have multiple attempts at running an operation before concluding there is an issue with the package. Please log an issue or pull request and send me your logfile if you run into a problem. logfiles are stored in `/src/tedata/logs`.

### Troubleshooting

On windows, if you get a permission denied error related to logging on package initialisation, such as:
```python
PermissionError: [Errno 13] Permission denied: 'c:\ProgramData\miniconda3\envs\ted\Lib\site-packages\tedata\logs\tedata.log
```
You need to run the package as administrator. Run VSCode or shell as admin.

Webscraping-based approaches to data acquisition can have errors resulting from the complexities of HTTP and browser interactions, which will not occur with consistent reproducibility. Due to the dynamic nature of web pages, network conditions, and browser states, errors that appear during one scraping attempt may not occur in subsequent attempts.

*It is recommended to make at least 3 attempts at an operation before concluding that an error is a legitimate issue with the package.*

There are a number of webdriver based errors that you may run into when attempting to download data. Generally, this is a result of stale webdriver objects being re-used. Create a new webdriver object and attempt the data download again. We create a new webdriver object by setting ```use_existing_driver = False``` on initilization of any of the webdriver containing objects such as ```TE_Scaper``` or ```search_TE```. If you encounter an error like this when using ```scrape_chart``` function, be sure to provide no webdriver or scraper object as a keyword argument and set ```use_existing_driver = False```. This will create a fresh webdriver when run. Sometimes it does work when re-using the same scraper object though, so can be worth trying.

#### Examples of stale webdriver error messages

- Error loading page: Message: Failed to decode response from marionette
- Error loading page: Message: Tried to run command without establishing a connection

```text
Error with the x-axis scraping & frequency deterination using Selenium and tooltips: Message: The element with the reference cd433d12-0d9a-4834-b50b-22e04ff49474 is stale; either its node document is not the active document, or it is no longer connected to the DOM; For documentation on this error, please visit: https://www.selenium.dev/documentation/webdriver/troubleshooting/errors#stale-element-reference-exception
Stacktrace:
RemoteError@chrome://remote/content/shared/RemoteError.sys.mjs:8:8
WebDriverError@chrome://remote/content/shared/webdriver/Errors.sys.mjs:193:5
StaleElementReferenceError@chrome://remote/content/shared/webdriver/Errors.sys.mjs:725:5
...
json.deserialize@chrome://remote/content/marionette/json.sys.mjs:297:10
receiveMessage@chrome://remote/content/marionette/actors/MarionetteCommandsChild.sys.mjs:
```
