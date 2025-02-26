import os
import sys
import logging
import speedtest
import time
import pandas as pd
import numpy as np
from datetime import datetime

wd = os.path.dirname(__file__); parent = os.path.dirname(wd); grampa = os.path.dirname(parent)
fdel = os.path.sep
sys.path.append(parent+fdel+"src")
print(parent+fdel+"src")

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
    
    # Configure console handler for test logger only
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(levelname)s - %(message)s')
    ch.setFormatter(console_formatter)
    
    # Add file handler to root logger to capture everything
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(fh)
    
    # Create test logger with console output
    logger = logging.getLogger('test_logger')
    logger.setLevel(logging.DEBUG)
    logger.addHandler(ch)
    logger.propagate = True  # Allow file logging via root logger
    
    # Prevent tedata logger from propagating to console
    tedata_logger.propagate = False
    tedata_logger.addHandler(fh)  # Add direct file handler
    
    # Log start of session
    logger.info("=== Test Session Started ===")
    
    return logger

# Create output directory at module level
output_dir = os.path.join(os.path.dirname(__file__), "test_runs")
os.makedirs(output_dir, exist_ok=True)
# Create single logger instance
logger = setup_test_logger(output_dir)

#### TEST FUNCTIONS ####
def test_internet_speed():
    """Test internet speed and return results"""
    try:
        logger.info("Testing internet speed...")
        
        st = speedtest.Speedtest()
        st.get_best_server()
        
        # Test download speed
        download_start = time.time()
        download_speed = st.download() / 1_000_000  # Convert to Mbps
        download_time = time.time() - download_start
        
        # Test upload speed
        upload_start = time.time()
        upload_speed = st.upload() / 1_000_000  # Convert to Mbps
        upload_time = time.time() - upload_start
        
        # Get ping
        ping = st.results.ping
        
        # Get server info
        server = st.results.server
        server_info = f"{server['sponsor']} ({server['name']}, {server['country']})"
        
        results = {
            'download_speed': round(download_speed, 2),
            'upload_speed': round(upload_speed, 2),
            'ping': round(ping, 2),
            'server': server_info,
            'download_test_time': round(download_time, 2),
            'upload_test_time': round(upload_time, 2)
        }
        
        logger.info(f"Internet speed test results:")
        logger.info(f"Download: {results['download_speed']} Mbps")
        logger.info(f"Upload: {results['upload_speed']} Mbps")
        logger.info(f"Ping: {results['ping']} ms")
        logger.info(f"Server: {results['server']}")
        
        return results
        
    except Exception as e:
        logger.error(f"Error testing internet speed: {str(e)}")
        return None

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
    
    for method in ["path", "tooltips", "mixed"]:
        try:
            logger.info(f"Testing {method} method")
            
            # Scrape data
            scraper =ted.scrape_chart(url, method=method)
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
            scraper.plot_series(show_fig=False)
            scraper.save_plot(filename=base_name, save_path=output_dir, format="html")
            
        except Exception as e:
            logger.error(f"Error testing {method} method: {str(e)}")
            continue
            
    # Compare results
    if len(results) == 3:
        series_match1 = compare_series(
            results["path"]["series"], 
            results["tooltips"]["series"],
            name=url)
        series_match2 = compare_series(results["path"]["series"], 
            results["mixed"]["series"],
            name=url)
        series_match3 = compare_series(results["tooltips"]["series"], 
            results["mixed"]["series"],
            name=url)
        
        metadata_match = compare_metadata(
            results["path"]["metadata"],
            results["mixed"]["metadata"],
            name=url
        )
        
        logger.info(f"Results for {url}:")
        logger.info(f"Series match: {series_match1}")
        logger.info(f"Series match: {series_match2}")
        logger.info(f"Series match: {series_match3}")
        logger.info(f"Metadata match: {metadata_match}")
        series_list = [{"series": results["path"]["series"], "add_name": "path"},
                       {"series": results["tooltips"]["series"], "add_name": "tooltips"},
                       {"series": results["mixed"]["series"], "add_name": "mixed"}] 

        # Make plot with all 3 traces
        ted.plot_multi_series(series_list=series_list, metadata = scraper.metadata, show_fig=True)
    
    return results

# Modify your main function
def main():
    """Run tests for all URLs"""
    logger.info("=== Starting Test Run ===")
    
    # Test internet speed first
    speed_results = test_internet_speed()
    
    logger.info("\nStarting scraping method comparison tests")
    
    all_results = {}
    for url in TEST_URLS:
        all_results[url] = test_url(url)
        
    logger.info("Tests completed")
    return all_results

if __name__ == "__main__":
    main()