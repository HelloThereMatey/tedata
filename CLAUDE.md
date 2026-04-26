# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

`tedata` scrapes macroeconomic time-series data from Trading Economics (tradingeconomics.com) using Selenium and BeautifulSoup. It extracts data from Highcharts-based SVG charts without requiring an API key.

**Key constraint**: Data is limited to 10 years maximum history due to Trading Economics anti-scraping measures.

## Architecture

### Core Classes

- **`Generic_Webdriver`** (`base.py`): Base class managing Selenium WebDriver lifecycle (Firefox/Chrome). Tracks active drivers for reuse.
- **`SharedWebDriverState`** (`base.py`): Observer pattern for syncing chart-related attributes (`page_source`, `chart_soup`, `date_span`, `chart_type`) between classes.
- **`TE_Scraper`** (`scraper.py`): Main scraping class. Inherits from both `Generic_Webdriver` and `SharedWebDriverState`. Handles page loading, chart interaction, data extraction, and metadata retrieval.
- **`TooltipScraper`** (`utils.py`): Extends `TE_Scraper` with cursor-based tooltip scraping for precise data extraction.
- **`search_TE`** (`search.py`): Searches Trading Economics website using the search bar and returns result URLs.

### Scraping Methods

1. **`highcharts_api`** (default): Extracts series data directly from the Highcharts JavaScript API via `series_from_highcharts()`. Fastest and most accurate.
2. **`path`**: Extracts SVG path pixel coordinates and scales them using y-axis values via `series_from_chart_soup()` + `scale_series()`.
3. **`tooltips`**: Drags cursor across chart to capture tooltip data via `full_series_fromTooltips()`.
4. **`mixed`**: Uses multiple chart date ranges to capture all data points via `tooltip_multiScrape()`. Slowest but most accurate.

### JavaScript Helpers (in `src/tedata/`)

- `check_highcharts.js`: Retrieves series data from Highcharts API
- `latest_points.js`: Cursor-based tooltip scraping across chart width
- `firstLastDates.js`: Gets first/last data points via tooltip
- `custom_datespan.js`: Sets date range via calendar widget
- `init_tooltips.js`: Initializes tooltip state

### Entry Points

- **`scrape_chart()`** (`scrape_chart.py`): Primary convenience function. Creates/uses a `TE_Scraper`, loads page, scrapes metadata, extracts series using specified method.
- **`search_TE.get_data()`** (`search.py`): Takes a search result index and calls `scrape_chart()` internally.

### Data Flow (highcharts_api method)

```
scrape_chart(url) → TE_Scraper.load_page(url) → scrape_metadata()
                  → series_from_highcharts() → reads Highcharts API via check_highcharts.js
                  → returns TE_Scraper with series + metadata
```

## Common Commands

```bash
# Install in development mode
pip install -e .

# Run CLI (downloads to current directory)
python -m tedata "https://tradingeconomics.com/united-states/ism-manufacturing-new-orders"

# CLI with visible browser
python -m tedata --head "https://tradingeconomics.com/united-states/ism-manufacturing-new-orders"

# CLI with alternative method
python -m tedata --method mixed "https://tradingeconomics.com/united-states/ism-manufacturing-new-orders"
```

## Python API Usage

```python
import tedata as ted

# Quick single-line scrape (recommended)
scraped = ted.scrape_chart(url="https://tradingeconomics.com/united-states/ism-manufacturing-new-orders")
print(scraped.series)

# Search and scrape
search = ted.search_TE()
search.search_trading_economics("ISM Manufacturing")
print(search.result_table)
scraped = search.get_data(1)  # Index into result_table
scraped.plot_series()
scraped.save_plot(format="html")

# Step-by-step (for reusing webdriver)
scr = ted.TE_Scraper(use_existing_driver=True)
scr.load_page(url)
scr.make_x_index()
scr.get_y_axis(set_global_y_axis=True)
scr.series_from_chart_soup()
scr.apply_x_index()
scr.scale_series()
scr.scrape_metadata()
```

## Key Attributes on TE_Scraper

- `series` (`pd.Series`): The time-series data with DatetimeIndex
- `metadata` (`dict`): Title, indicator, country, units, source, date range, frequency, etc.
- `series_metadata` (`pd.Series`): metadata as a Series
- `y_axis` (`pd.Series`): Y-axis tick labels (index=pixel heights, values=display values)
- `x_index` (`pd.DatetimeIndex`): Generated datetime index for the series
- `date_spans` (`dict`): Available date range buttons on chart (MAX, 10Y, 5Y, etc.)
- `chart_types` (`dict`): Available chart type buttons (Line, Spline, Column, etc.)

## Browser Requirement

**Firefox only** is currently supported. The package requires `geckodriver` and Firefox to be installed system-wide at `/usr/bin/firefox` and `/usr/bin/geckodriver`.

## Environment Variables

- `TEDATA_DISABLE_LOGGING=true`: Disables all logging output (useful on Windows with permission issues)

## Logging

Logs are written to `src/tedata/logs/tedata.log`. On Windows, run as administrator if you encounter permission denied errors on the log file.
