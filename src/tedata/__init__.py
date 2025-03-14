import pandas as pd
import sys
import datetime
from .logger_setup import setup_logger

# Set plotly as the default plotting backend for pandas
pd.options.plotting.backend = "plotly"

# Version of the tedata package
__version__ = "0.3.0"

# Setup logger first
logger = setup_logger()

# Then import modules
from .base import *
from .utils import *
from .scraper import *
from .search import *
from .scrape_chart import *

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