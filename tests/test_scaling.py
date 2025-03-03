import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os
import sys

wd = os.path.dirname(__file__); parent = os.path.dirname(wd); grampa = os.path.dirname(parent)
fdel = os.path.sep
sys.path.append(parent+fdel+"src")

import tedata as ted
    

class TestScalingPlotSimp(plt.Figure):
    """
    A matplotlib Figure subclass for visualizing the scaling process
    in the TE_Scraper class.
    """
    
    def __init__(self, scraper, figsize=(10, 6)):
        super().__init__(figsize=figsize)
        self.scraper = scraper
        self.ax = self.add_subplot(111)
        
    
    def plot_em(self):
        """
        Plot the scaling process for the EM method.
        """
        # Plot unscaled series with inverted y-axis
        if hasattr(self.scraper, "unscaled_series"):
            self.ax.plot(self.scraper.unscaled_series.index, self.scraper.unscaled_series.values, 
                      'b-', label='Unscaled data')
            self.ax.invert_yaxis()  # Invert y-axis for pixel coordinates
            
        # Add horizontal lines for y-axis values
        if hasattr(self.scraper, "y_axis"):
            for px_pos, value in zip(self.scraper.y_axis.index, self.scraper.y_axis.values):
                self.ax.axhline(y=px_pos, color='r', linestyle='--', alpha=0.5)
                self.ax.text(min(self.scraper.unscaled_series.index)-5, px_pos, 
                          f"{value}", va='center', ha='right')
                
        # Add basic annotations
        self.ax.set_title('Scaling Visualization')
        self.ax.set_xlabel('X-axis (Pixel Coordinates)')
        self.ax.set_ylabel('Y-axis (Pixel Coordinates)')
        self.ax.grid(True, alpha=0.3)
        self.tight_layout()

    def show(self):
        plt.show()


if __name__ == "__main__":
    # Test the scaling plot
    url = 'https://tradingeconomics.com/united-states/personal-income'
    scr = ted.TE_Scraper(use_existing_driver = False, headless = True)  ## Initialize a new TE_scraper object.
    scr.load_page(url, extra_wait_time=5) 

    scr.scrape_metadata() ## Scrape the metadata for the data series from the page.
    scr.make_x_index(force_rerun_freqdet=True, force_rerun_xlims=True)
    scr.get_y_axis(set_global_y_axis=True) 
    scr.series_from_chart_soup(set_max_datespan=True)
    scr.apply_x_index()
    
    # Create scaling plot
    scaling_plot = TestScalingPlotSimp(scraper = scr)
    scaling_plot.plot_em()
    scaling_plot.show()