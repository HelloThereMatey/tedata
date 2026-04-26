"""
Retry failed tests from test_indicators_100.py using highcharts_api method
and both browsers to diagnose whether the issue is URL-specific or method/browser-specific.

Run with: python tests/retry_failures.py
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
logger = logging.getLogger('retry_failures')

# Failed indices from test_results_summary.csv
FAILED_INDICES = [72, 74, 80, 84, 92, 93, 94, 96, 98]

# Load original indicators
INDICATORS_CSV = 'tests/TE_indicators_100.csv'
df_all = pd.read_csv(INDICATORS_CSV)

# Load original results
df_orig = pd.read_csv('tests/test_results_summary.csv')

results = []

print("\n" + "="*80)
print("RETRY FAILED TESTS")
print("="*80)

for orig_idx in FAILED_INDICES:
    row = df_orig[df_orig['idx'] == orig_idx].iloc[0]
    url = row['url']
    original_method = row['method']
    original_browser = row['browser']

    print(f"\n--- idx {orig_idx}: {url} ---")
    print(f"    Original: {original_method}/{original_browser} -> {row['status']}")

    # Try highcharts_api with both browsers
    for browser in ['chrome', 'firefox']:
        method = 'highcharts_api'
        start_time = time.time()
        status = 'pending'
        error = None
        series_len = None
        start_date = None
        end_date = None

        try:
            logger.info(f"[{orig_idx}] Testing {url} with {method}/{browser}")
            scraper = scrape_chart(
                url=url,
                method=method,
                browser=browser,
                headless=True,
                use_existing_driver=False,
            )

            if scraper is not None and hasattr(scraper, 'series') and scraper.series is not None:
                status = 'success'
                series_len = len(scraper.series)
                start_date = str(scraper.series.index[0].date()) if len(scraper.series) > 0 else None
                end_date = str(scraper.series.index[-1].date()) if len(scraper.series) > 0 else None
                logger.info(f"[{orig_idx}] SUCCESS with {method}/{browser}: {series_len} pts")
            else:
                status = 'failed'
                error = 'Scraper returned None or no series'
                logger.warning(f"[{orig_idx}] FAILED with {method}/{browser}")

        except Exception as e:
            status = 'error'
            error = str(e)[:200]
            logger.error(f"[{orig_idx}] ERROR with {method}/{browser}: {e}")

        duration_s = round(time.time() - start_time, 1)

        result_row = {
            'orig_idx': orig_idx,
            'url': url,
            'method': method,
            'browser': browser,
            'status': status,
            'error': error,
            'series_len': series_len,
            'start_date': start_date,
            'end_date': end_date,
            'duration_s': duration_s,
        }
        results.append(result_row)

        # Close scraper
        if 'scraper' in locals() and scraper is not None:
            try:
                scraper.close()
            except Exception:
                pass

        time.sleep(2)

# Save results
df_results = pd.DataFrame(results)
df_results.to_csv('tests/retry_failures_summary.csv', index=False)

# Print summary
print("\n" + "="*80)
print("RETRY RESULTS")
print("="*80)

for _, row in df_results.iterrows():
    icon = "OK" if row['status'] == 'success' else "FAIL"
    print(f"  [{row['orig_idx']:3d}] {row['method']}/{row['browser']}: {icon} - {row['status']} "
          f"{row['series_len'] or 0}pts ({row['start_date'] or '?'} to {row['end_date'] or '?'}) - {row['error'] or ''}")

success = (df_results['status'] == 'success').sum()
print(f"\nSuccess: {success}/{len(df_results)}")

# Group by URL to see if any URL works
print("\nBy URL:")
for orig_idx in FAILED_INDICES:
    subset = df_results[df_results['orig_idx'] == orig_idx]
    successes = (subset['status'] == 'success').sum()
    url = subset.iloc[0]['url']
    print(f"  idx {orig_idx}: {successes}/{len(subset)} browsers succeeded - {url}")

print(f"\nResults saved to: tests/retry_failures_summary.csv")
