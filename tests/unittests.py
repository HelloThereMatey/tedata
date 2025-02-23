import unittest
import os
import sys
import logging
import pandas as pd
import numpy as np
from datetime import datetime

# Add parent directory to path to import tedata
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tedata import scrape_chart
wd = os.path.dirname(__file__)
fdel = os.path.sep

#List of urls to test
with open(wd+fdel+"test_urls.csv", "r") as f:
    TEST_URLS = [line.strip() for line in f.readlines()]

class TestTEDataScraping(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test environment once for all tests"""
        cls.output_dir = os.path.join(os.getcwd(), "test_runs")
        os.makedirs(cls.output_dir, exist_ok=True)
        
        # Setup logging
        logging.getLogger('selenium').setLevel(logging.WARNING)
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        
        cls.logger = cls.setup_test_logger(cls.output_dir)

    @staticmethod
    def setup_test_logger(output_dir):
        """Set up logger for test runs"""
        log_file = os.path.join(
            output_dir,
            f'scraping_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        )
        fh = logging.FileHandler(log_file)
        fh.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - TEST - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        logger = logging.getLogger('test_logger')
        logger.addHandler(fh)
        return logger

    def test_series_attributes(self):
        """Test series attributes match between methods"""
        for url in TEST_URLS:
            with self.subTest(url=url):
                self.logger.info(f"\nTesting URL: {url}")
                
                # Get data using both methods
                path_scraper = scrape_chart(url, method="path")
                tooltip_scraper = scrape_chart(url, method="tooltips")
                
                # Basic existence checks
                self.assertIsNotNone(path_scraper, "Path scraper failed to initialize")
                self.assertIsNotNone(tooltip_scraper, "Tooltip scraper failed to initialize")
                
                # Check series existence and type
                self.assertTrue(hasattr(path_scraper, 'series'), "Path scraper missing series")
                self.assertTrue(hasattr(tooltip_scraper, 'series'), "Tooltip scraper missing series")
                self.assertIsInstance(path_scraper.series, pd.Series)
                self.assertIsInstance(tooltip_scraper.series, pd.Series)
                
                # Compare series lengths
                self.assertEqual(
                    len(path_scraper.series), 
                    len(tooltip_scraper.series),
                    "Series lengths don't match"
                )
                
                # Compare index types and values
                self.assertTrue(
                    path_scraper.series.index.equals(tooltip_scraper.series.index),
                    "Series indices don't match"
                )
                
                # Compare values with tolerance
                np.testing.assert_allclose(
                    path_scraper.series.values,
                    tooltip_scraper.series.values,
                    rtol=1e-3,
                    err_msg="Series values don't match within tolerance"
                )
                
                # Export results
                base_name = url.split('/')[-1]
                for scraper, method in [(path_scraper, "path"), (tooltip_scraper, "tooltips")]:
                    scraper.export_data(
                        savePath=self.output_dir, 
                        filename=f"{base_name}_{method}"
                    )
                    scraper.save_plot(
                        filename=f"{base_name}_{method}",
                        save_path=self.output_dir,
                        format="html"
                    )

    def test_metadata_attributes(self):
        """Test metadata attributes match between methods"""
        for url in TEST_URLS:
            with self.subTest(url=url):
                self.logger.info(f"\nTesting metadata for URL: {url}")
                
                path_scraper = scrape_chart(url, method="path")
                tooltip_scraper = scrape_chart(url, method="tooltips")
                
                # Check metadata existence
                self.assertTrue(hasattr(path_scraper, 'metadata'))
                self.assertTrue(hasattr(tooltip_scraper, 'metadata'))
                
                # Compare metadata keys
                self.assertEqual(
                    set(path_scraper.metadata.keys()),
                    set(tooltip_scraper.metadata.keys()),
                    "Metadata keys don't match"
                )
                
                # Compare metadata values
                for key in path_scraper.metadata:
                    self.assertEqual(
                        path_scraper.metadata[key],
                        tooltip_scraper.metadata[key],
                        f"Metadata value mismatch for key: {key}"
                    )

if __name__ == '__main__':
    unittest.main(verbosity=2)