import os 

##### Get the directory where this file is housed ########################
wd = os.path.dirname(__file__)
fdel= os.path.sep

import argparse
from . import scrape_chart
import pandas as pd

def main():
    # Create parser
    parser = argparse.ArgumentParser(
        description='Scrape data from Trading Economics charts'
    )
    
    # Add arguments
    parser.add_argument(
        'url',
        type=str,
        help='URL of Trading Economics chart to scrape'
    )
    
    # Optional arguments
    parser.add_argument(
        '--head',
        '-he',
        action='store_false',
        help='Run browser with head i.e show the browser window. Default is headless/hidden window.'
    )

    parser.add_argument(
        '--method',
        '-m',
        choices=["path", "tooltips", "mixed", "highcharts_api"],
        help='Scraping method to use: "path", "tooltips" or "mixed". If not specified, default method "highcharts_api" will be used.'
    )

    # Parse arguments
    args = parser.parse_args()
    
    try:
        # Run scraper
        result = scrape_chart(url=args.url, use_existing_driver = False, headless=args.head, method=args.method)
        
        if result is not None:
            # Create output filename from URL
            filename = args.url.split('/')[-2] + '_' + args.url.split('/')[-1] + '.xlsx'
            
            # Create Excel writer
            with pd.ExcelWriter(filename) as writer:
                # Save series data
                result.series.to_excel(writer, sheet_name='Data')
                # Save metadata
                result.series_metadata.to_excel(writer, sheet_name='Metadata')
            
            print(f"\n\nData saved to {filename}")
            result.plot_series()  #Plot the data in an interactive html plotly chart.
        else:
            print("Error: Scraping failed")
            
    except Exception as e:
        print(f"Error: {str(e)}")

    result.close()
    del result

if __name__ == '__main__':
    main()