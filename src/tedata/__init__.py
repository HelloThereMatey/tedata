import pandas as pd
import sys
import datetime
import os
from .logger_setup import setup_logger

# Set plotly as the default plotting backend for pandas
pd.options.plotting.backend = "plotly"

# Version of the tedata package
__version__ = "0.3.51"

# Check for environment variable to disable logging
disable_logging = os.environ.get('TEDATA_DISABLE_LOGGING', '').lower() in ('true', '1', 'yes')

# Setup logger with disable option
logger = setup_logger(disable_logging=disable_logging)

# Then import modules
from .base import *
from .utils import *
from .scraper import *
from .search import *
from .scrape_chart import *

# Only log if logging is enabled
if not disable_logging:
    ## Check browser installation
    firefox, chrome = check_browser_installed()
    logger.debug(f"""
    New initialization of the tedata package:
    Version: {__version__}
    Python: {sys.version}
    System: {sys.platform}
    Location: {os.path.dirname(__file__)}
    Time: {datetime.datetime.now()}
    User: {os.getlogin()}
    Browsers:
    - Firefox: {firefox}
    - Chrome: {chrome}
    """)
    logger.info(f"tedata package initialized successfully!")
else:
    # Still check browser installation but don't log it
    firefox, chrome = check_browser_installed()

# Add this to your /src/tedata/__init__.py file

def configure(disable_logging=None):
    """
    Configure tedata package settings
    
    Args:
        disable_logging (bool): If True, suppresses all logging output
                               If False, enables normal logging
                               If None (default), doesn't change current setting
    """
    global logger
    
    # Only update logger if a value was provided
    if disable_logging is not None:
        # Reconfigure logger with new setting
        logger = setup_logger(disable_logging=disable_logging)
        
        # Update environment variable for consistency
        if disable_logging:
            os.environ['TEDATA_DISABLE_LOGGING'] = 'true'
        else:
            os.environ['TEDATA_DISABLE_LOGGING'] = 'false'