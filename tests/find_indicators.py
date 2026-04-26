"""
Harvest up to 100 Trading Economics indicators across multiple categories,
save to CSV for test battery use.
Run with: python tedata_local/find_indicators.py
"""

import os
os.chdir("/home/totabilcat/Documents/Code/Bootleg_Macro")
import sys
sys.path.append(os.getcwd())

import tedata
from tedata.search import search_TE
import pandas as pd
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('find_indicators')


# Load search terms from CSV
SEARCH_TERMS_CSV = 'User_Data/TE_search_terms.csv'
df_terms = pd.read_csv(SEARCH_TERMS_CSV)
SEARCH_TERMS = df_terms['search_term'].tolist()


# Prepare to collect top result URLs
top_results = []

for term in SEARCH_TERMS:
    url = None
    try:
        search = search_TE(load_homepage=True)
        search.search_trading_economics(term, wait_time=3)
        if hasattr(search, 'result_table') and search.result_table is not None and not search.result_table.empty:
            url = search.result_table.iloc[0]['url']
            logger.info(f"Top result for '{term}': {url}")
        else:
            logger.info(f"No results for: {term}")
    except Exception as e:
        logger.error(f"Error searching '{term}': {e}")
    top_results.append(url)
    time.sleep(0.5)

# Save results to new CSV with search_term and url columns
df_terms['url'] = top_results
out_path = 'User_Data/TE_indicators_100.csv'
df_terms.to_csv(out_path, index=False)
print(f"\nSaved {len(df_terms)} search terms and URLs → {out_path}")
print(df_terms.head(20).to_string())