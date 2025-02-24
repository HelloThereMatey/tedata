import os
import sys
import logging
import pandas as pd
import numpy as np
from datetime import datetime

wd = os.path.dirname(__file__); parent = os.path.dirname(wd); grampa = os.path.dirname(parent)
fdel = os.path.sep
sys.path.append(parent+fdel+"src")
print(parent+fdel+"src")

from tedata import base
import tedata as ted

# Add parent directory to path to import tedata
#List of urls to test
with open(wd+fdel+"test_urls.csv", "r") as f:
    TEST_URLS = [line.strip() for line in f.readlines()]
print("Test URLS for which to download data: ",TEST_URLS)

def setup_test_logger(output_dir):
    """Set up logger for test runs with both file and console output"""
    # Disable selenium logging
    logging.getLogger('selenium').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)

    # Create timestamped log filename
    log_file = os.path.join(
        output_dir,
        f'scraping_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
    )
    
    # Get root logger and tedata logger
    root_logger = logging.getLogger()
    tedata_logger = logging.getLogger('tedata')
    
    # Clear all existing handlers
    root_logger.handlers.clear()
    tedata_logger.handlers.clear()
    
    # Configure file handler for all logging
    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(file_formatter)
    
    # Configure console handler for all loggers
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(console_formatter)
    
    # Set up root logger to capture everything
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(fh)
    root_logger.addHandler(ch)  # Add console handler to root logger
    
    # Create test logger
    logger = logging.getLogger('test_logger')
    logger.setLevel(logging.DEBUG)
    logger.propagate = True  # Allow propagation to root logger
    
    # Allow tedata logger to propagate to root logger
    tedata_logger.propagate = True
    
    # Log start of session
    logger.info("=== Test Session Started ===")
    
    return logger

# Create output directory at module level
output_dir = os.path.join(os.path.dirname(__file__), "test_runs")
os.makedirs(output_dir, exist_ok=True)
# Create single logger instance
logger = setup_test_logger(output_dir)

#### TEST FUNCTIONS ####
def compare_series(series1, series2, name=""):
    """Compare two series and log differences"""
    try:
        if len(series1) != len(series2):
            logger.warning(f"{name} - Different lengths: {len(series1)} vs {len(series2)}")
            return False
            
        # Compare index
        if not series1.index.equals(series2.index):
            logger.warning(f"{name} - Index mismatch")
            logger.debug(f"Index diff: {series1.index.difference(series2.index)}")
            return False
            
        # Compare values with tolerance
        value_match = np.allclose(series1.values, series2.values, rtol=1e-3, equal_nan=True)
        if not value_match:
            logger.warning(f"{name} - Value mismatch")
            diff = (series1 - series2).abs()
            logger.debug(f"Max difference: {diff.max()}")
            return False
            
        return True
    except Exception as e:
        logger.error(f"Error comparing series: {str(e)}")
        return False

def compare_metadata(meta1, meta2, name=""):
    """Compare two metadata dictionaries"""
    try:
        if meta1.keys() != meta2.keys():
            logger.warning(f"{name} - Different metadata keys")
            return False
            
        for key in meta1:
            if meta1[key] != meta2[key]:
                logger.warning(f"{name} - Metadata mismatch for key: {key}")
                logger.debug(f"{meta1[key]} vs {meta2[key]}")
                return False
                
        return True
    except Exception as e:
        logger.error(f"Error comparing metadata: {str(e)}")
        return False

def test_url(url):
    """Test scraping methods for a single URL"""
    # Remove logger setup from here since we're using the global one
    logger.info(f"Testing URL: {url}")
    
    results = {}
    
    for method in ["path", "tooltips"]:
        try:
            logger.info(f"Testing {method} method for {url}")
            
            # Scrape data
            scraper =ted.scrape_chart(url, method=method, use_existing_driver=False, headless=True)
            if scraper is None:
                logger.error(f"{method} method failed to return scraper")
                continue
                
            # Store results
            results[method] = {
                'series': scraper.series.copy() if hasattr(scraper, 'series') else None,
                'metadata': scraper.metadata.copy() if hasattr(scraper, 'metadata') else None
            }
            
            # Export data and plot
            base_name = f"{url.split('/')[-1]}_{method}"
            scraper.export_data(savePath=output_dir, filename=base_name)
            scraper.plot_series()
            scraper.save_plot(filename=base_name, save_path=output_dir, format="html")
            
        except Exception as e:
            logger.error(f"Error testing {method} method: {str(e)}")
            continue
            
    # Compare results
    if len(results) == 2:
        series_match = compare_series(
            results["path"]["series"], 
            results["tooltips"]["series"],
            name=url
        )
        metadata_match = compare_metadata(
            results["path"]["metadata"],
            results["tooltips"]["metadata"],
            name=url
        )
        
        logger.info(f"Results for {url}:")
        logger.info(f"Series match: {series_match}")
        logger.info(f"Metadata match: {metadata_match}")
        
    return results

def main():
    """Run tests for all URLs"""
    logger.info("Starting scraping method comparison tests")
    
    all_results = {}
    for url in TEST_URLS:
        all_results[url] = test_url(url)
        base.find_active_drivers(quit_all=True)
        
    logger.info("Tests completed")
    return all_results

if __name__ == "__main__":
    main()