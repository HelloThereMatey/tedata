import os
import sys
import logging
import speedtest
import time
import timeit
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
with open(wd+fdel+"test_urls_all.csv", "r") as f:
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
    result_summary = pd.DataFrame(columns = ["URL", "Method", "Returned scraper", "Time taken", "Error", "% deviation from mixed method", "Series length", "Length metadata"])
    blank_metadata = pd.Series(np.nan, 
    index = ['units', 'original_source', 'title', 'indicator', 'country', 'source', 'id', 'description', 'frequency', 'unit_tooltips', 'start_date', 'end_date', 'min_value', 'max_value', 'length'],
    name="blank")
    
    for i, method in enumerate(["mixed", "path", "tooltips"]):
        succeded = True
        base_name = url.split('/')[-2]+"_"+url.split('/')[-1]+"_"+method
        try:
            error = "No error"
            logger.info(f"Testing {method} method for {url}")
            
            # Scrape data
            timer = timeit.default_timer()
            scraper = ted.scrape_chart(url, method=method, use_existing_driver=False, headless=True)
            if scraper is None:
                logger.error(f"{method} method failed to return scraper")
                error = "No scraper returned"
                succeded = False
            if scraper.series.empty or scraper.series.isna().all():
                logger.error(f"{method} method returned empty series")
                error = "Empty series"
                succeded = False
            elapsed = timeit.default_timer() - timer

            series = scraper.series.rename(base_name).copy() if scraper is not None and hasattr(scraper, 'series') else pd.Series(np.nan, name=base_name, index = [0, 1, 2, 3])
            metadata = scraper.series_metadata.rename(base_name).copy() if scraper is not None and hasattr(scraper, 'series') and hasattr(scraper, 'metadata') else blank_metadata.rename(base_name).copy()
       
        except Exception as e:
            logger.error(f"Error downloading data for {url} using method: {method}, error: {str(e)}")
            succeded = False
            error = str(e)
            series = pd.Series(np.nan, name=base_name, index = [0, 1, 2, 3])
            metadata = blank_metadata.rename(base_name).copy()
            elapsed = timeit.default_timer() - timer

        logger.info(f"scrape_chart method took: {elapsed:.2f} seconds to complete for {url} using method {method} and it succeded: {succeded}.")
        # Store results
        results[method] = {'series': series, 'metadata': metadata}
        result_summary = pd.concat([result_summary, pd.DataFrame({
                "URL": [url],
                "Method": [method],
                "Returned scraper": [succeded],
                "Time taken": [f"{elapsed:.2f}"],
                "Error": [error],
                "% deviation from mixed method": [""],
                "Series length": [len(series)],
                "Length metadata": [len(metadata)]})], ignore_index=True)
            
        if i == 0:
            output_df = series
            output_meta_df = metadata
        else:
            output_df = pd.concat([output_df, series], axis=1)
            output_meta_df = pd.concat([output_meta_df, metadata], axis=1)
    
    # Outside for loop here..
    metadata_match = compare_metadata(results["path"]["metadata"], results["mixed"]["metadata"], name=url)
    
    # Make plot with all 3 traces
    logger.info(f"Results for {url}:")
    logger.info(f"Metadata match: {metadata_match}")

    with pd.ExcelWriter(output_dir+fdel+f"{url.split('/')[-2]}_{url.split('/')[-1]}.xlsx") as writer:
        output_df.to_excel(writer, sheet_name="Data")
        output_meta_df.to_excel(writer, sheet_name="Metadata")
    
    for method in ["mixed", "path", "tooltips"]:
        pctdev = (((results[method]["series"]/results["mixed"]["series"])-1)*100).dropna().mean()
        result_summary.loc[result_summary["Method"]==method, "% deviation from mixed method"] = pctdev

    series_list = [{"series": results["path"]["series"], "add_name": "path"},
                    {"series": results["tooltips"]["series"], "add_name": "tooltips"},
                    {"series": results["mixed"]["series"], "add_name": "mixed"}] 
    triplefig = ted.plot_multi_series(series_list=series_list, metadata = scraper.metadata, show_fig=False, return_fig=True)
    triplefig.write_html(f"{output_dir}{fdel}{url.split('/')[-2]}_{url.split('/')[-1]}.html")
    logger.info(f"Plot saved as {output_dir}{fdel}{url.split('/')[-2]}_{url.split('/')[-1]}.html")

    return result_summary 

def generate_html_report(test_results_df, output_dir):
    """
    Generate a comprehensive HTML report with test results and all interactive plots.
    
    Args:
        test_results_df: DataFrame with test results
        output_dir: Directory with plot files
    """
    # Create HTML string
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Trading Economics Scraper Test Results</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            h1, h2 { color: #2c3e50; }
            table { border-collapse: collapse; width: 100%; margin-bottom: 30px; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            th { background-color: #f2f2f2; }
            tr:nth-child(even) { background-color: #f9f9f9; }
            .figure-container { margin-bottom: 40px; border: 1px solid #ddd; padding: 15px; }
            .methods-comparison { display: flex; justify-content: space-between; margin-bottom: 10px; }
            .method-stats { flex: 1; margin: 0 10px; padding: 10px; background-color: #f9f9f9; }
            .plotly-iframe { width: 100%; height: 600px; border: none; }
        </style>
    </head>
    <body>
        <h1>Trading Economics Scraper Test Results</h1>
        <h2>Overall Summary</h2>
    """
    
    # Add test results table
    html += "<h3>Method Comparison Results</h3>"
    html += test_results_df.to_html(index=False)
    
    # Add each plot with its metadata
    html += "<h2>Individual Chart Results</h2>"
    
    # Group results by URL
    urls = test_results_df['URL'].unique()
    
    for url in urls:
        url_name = url.split('/')[-2] + '_' + url.split('/')[-1]
        html += f"<div class='figure-container'>"
        html += f"<h3>Results for: {url}</h3>"
        
        # Add URL-specific stats
        url_results = test_results_df[test_results_df['URL'] == url]
        html += "<div class='methods-comparison'>"
        
        for _, row in url_results.iterrows():
            html += f"""
            <div class='method-stats'>
                <h4>{row['Method']} Method</h4>
                <p>Time: {row['Time taken']} seconds</p>
                <p>Status: {"✓ Success" if row['Returned scraper'] else "✗ Failed"}</p>
                <p>Error: {row['Error']}</p>
                <p>Deviation: {row['% deviation from mixed method']}</p>
            </div>
            """
        html += "</div>"
        
        # Find the matching plot file
        plot_file = url_name + '.html'
        plot_path = os.path.join(output_dir, plot_file)
        
        if os.path.exists(plot_path):
            # Simply embed the entire figure as an iframe
            relative_path = os.path.relpath(plot_path, output_dir)
            html += f'<iframe src="{relative_path}" class="plotly-iframe"></iframe>'
        else:
            html += f"<p>Plot file not found: {plot_file}</p>"
        
        html += "</div>"  # Close figure-container
    
    # Close HTML document
    html += """
    </body>
    </html>
    """
    
    # Write to file
    report_path = os.path.join(output_dir, "complete_report.html")
    with open(report_path, 'w') as f:
        f.write(html)
    
    print(f"Complete HTML report saved to {report_path}")
    return report_path

# Modify your main function
def main():
    """Run tests for all URLs"""
    logger.info("=== Starting Test Run ===")
    
    # Test internet speed first
    test_internet_speed()
    
    logger.info("\nStarting scraping method comparison tests")
    
    all_results = pd.DataFrame(columns = ["URL", "Method", "Returned scraper", "Time taken", "Error", "% deviation from mixed method"])
    for url in TEST_URLS:
        all_results = pd.concat([all_results, test_url(url)], ignore_index=True)    
        base.find_active_drivers(quit_all=True)
        
    logger.info("Tests completed")
    return all_results

if __name__ == "__main__":
    tests = main()
    tests.to_markdown(output_dir+fdel+"test_results.md", index=False)
    tests.to_csv(output_dir+fdel+"test_results.csv", index=False)
    logger.info("=== Test Run Completed ===")

    ## Generate HTML report of the test results
    output_dir = wd+fdel+"test_runs"
    test_results_df = pd.read_csv(output_dir+fdel+"test_results.csv")
    print(test_results_df)
    generate_html_report(test_results_df, output_dir)