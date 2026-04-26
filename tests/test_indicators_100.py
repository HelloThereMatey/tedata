"""
Test battery for 100 Trading Economics indicators.
Distributes tests across methods and browsers:
- 20% highcharts_api + chrome (indices 0-19)
- 20% highcharts_api + firefox (indices 20-39)
- 60% distributed: path, tooltips, mixed with alternating browsers (indices 40-99)

Run with: python tests/test_indicators_100.py
"""

import os
os.chdir("/home/totabilcat/Documents/Code/tedata")
import sys
sys.path.insert(0, os.getcwd())

import tedata
from tedata.scrape_chart import scrape_chart
import pandas as pd
import logging
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('test_indicators_100')

# ── Load indicators ─────────────────────────────────────────────────────────────
INDICATORS_CSV = 'tests/TE_indicators_100.csv'
df = pd.read_csv(INDICATORS_CSV)
urls = df['url'].tolist()

# ── Test config ─────────────────────────────────────────────────────────────────
METHODS = ['highcharts_api', 'path', 'tooltips', 'mixed']
BROWSERS = ['chrome', 'firefox']

# Distribution:
# 0-19:   highcharts_api + chrome
# 20-39:  highcharts_api + firefox
# 40-59:  path + alternating chrome/firefox
# 60-79:  tooltips + alternating chrome/firefox
# 80-99:  mixed + alternating chrome/firefox

def get_method_browser(idx):
    if idx < 20:
        return 'highcharts_api', 'chrome'
    elif idx < 40:
        return 'highcharts_api', 'firefox'
    elif idx < 60:
        browser = 'chrome' if idx % 2 == 0 else 'firefox'
        return 'path', browser
    elif idx < 80:
        browser = 'chrome' if idx % 2 == 0 else 'firefox'
        return 'tooltips', browser
    else:
        browser = 'chrome' if idx % 2 == 0 else 'firefox'
        return 'mixed', browser

# ── Results tracking ────────────────────────────────────────────────────────────
results = []

SERIES_FILE = 'tests/results_series.h5'
METADATA_FILE = 'tests/results_metadata.h5'

# Clear old files
for f in [SERIES_FILE, METADATA_FILE]:
    if os.path.exists(f):
        os.remove(f)

def save_checkpoint(results, series_store, metadata_store):
    """Save current results to HDF5 and write summary CSV."""
    df_results = pd.DataFrame(results)
    df_results.to_csv('tests/test_results_summary.csv', index=False)
    with pd.HDFStore(SERIES_FILE) as store:
        store.put('results_summary', df_results)
    with pd.HDFStore(METADATA_FILE) as store:
        store.put('results_summary', df_results)

# ── Run tests ───────────────────────────────────────────────────────────────────
total = 0
for i, url in enumerate(urls):
    method, browser = get_method_browser(i)
    row = {
        'idx': i,
        'url': url,
        'method': method,
        'browser': browser,
        'status': 'pending',
        'error': None,
        'series_len': None,
        'start_date': None,
        'end_date': None,
        'duration_s': None,
    }

    start_time = time.time()
    try:
        logger.info(f"[{i+1}/100] Testing {url} with {method}/{browser}")
        scraper = scrape_chart(
            url=url,
            method=method,
            browser=browser,
            headless=True,
            use_existing_driver=False,
        )

        if scraper is not None and hasattr(scraper, 'series') and scraper.series is not None:
            row['status'] = 'success'
            row['series_len'] = len(scraper.series)
            row['start_date'] = str(scraper.series.index[0].date()) if len(scraper.series) > 0 else None
            row['end_date'] = str(scraper.series.index[-1].date()) if len(scraper.series) > 0 else None

            # Save series to HDF5
            series_key = f"idx_{i:03d}_{scraper.metadata.get('indicator', 'unknown').replace(' ', '_')[:30]}"
            with pd.HDFStore(SERIES_FILE) as store:
                store.put(series_key, scraper.series)

            # Save metadata to HDF5
            if hasattr(scraper, 'series_metadata') and scraper.series_metadata is not None:
                with pd.HDFStore(METADATA_FILE) as store:
                    store.put(series_key, scraper.series_metadata)

            logger.info(f"[{i+1}/100] SUCCESS: {url} -> {row['series_len']} points, {row['start_date']} to {row['end_date']}")
        else:
            row['status'] = 'failed'
            row['error'] = 'Scraper returned None or no series'
            logger.warning(f"[{i+1}/100] FAILED: {url} -> {row['error']}")

    except Exception as e:
        row['status'] = 'error'
        row['error'] = str(e)[:200]
        logger.error(f"[{i+1}/100] ERROR: {url} -> {e}")

    row['duration_s'] = round(time.time() - start_time, 1)
    results.append(row)
    total += 1

    # Close scraper to free resources
    if 'scraper' in locals() and scraper is not None:
        try:
            scraper.close()
        except Exception:
            pass

    # Brief pause between tests
    time.sleep(1)

    # Checkpoint every 10 iterations
    if (i + 1) % 10 == 0:
        logger.info(f"[{i+1}/100] Checkpoint - saving results")
        save_checkpoint(results, SERIES_FILE, METADATA_FILE)

# ── Build summary table ──────────────────────────────────────────────────────────
save_checkpoint(results, SERIES_FILE, METADATA_FILE)

# ── Print summary ───────────────────────────────────────────────────────────────
df_results = pd.DataFrame(results)
success = (df_results['status'] == 'success').sum()
failed = (df_results['status'] == 'failed').sum()
errors = (df_results['status'] == 'error').sum()

print("\n" + "="*80)
print("TEST BATTERY SUMMARY")
print("="*80)
print(f"Total tests: {total}")
print(f"Success: {success} ({100*success/total:.1f}%)")
print(f"Failed: {failed} ({100*failed/total:.1f}%)")
print(f"Errors: {errors} ({100*errors/total:.1f}%)")
print("="*80)

# By method
print("\nBy Method:")
for method in METHODS:
    subset = df_results[df_results['method'] == method]
    s = (subset['status'] == 'success').sum()
    print(f"  {method:20s}: {s}/{len(subset)} success ({100*s/len(subset):.1f}%)" if len(subset) > 0 else f"  {method:20s}: no tests")

# By browser
print("\nBy Browser:")
for browser in BROWSERS:
    subset = df_results[df_results['browser'] == browser]
    s = (subset['status'] == 'success').sum()
    print(f"  {browser:10s}: {s}/{len(subset)} success ({100*s/len(subset):.1f}%)")

# Failures/errors
print("\nFailures and Errors:")
for _, row in df_results.iterrows():
    if row['status'] != 'success':
        print(f"  [{row['idx']:3d}] {row['method']}/{row['browser']}: {row['status']} - {row['error'][:80]}")

print(f"\nResults saved to: tests/test_results_summary.csv")
print(f"Series saved to:   {SERIES_FILE}")
print(f"Metadata saved to: {METADATA_FILE}")