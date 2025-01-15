#  __init__.py

import pandas as pd

# Set plotly as the default plotting backend for pandas
pd.options.plotting.backend = "plotly"

# Version of the tedata package
__version__ = "0.10"

# Importing all the modules
from .scraper import *
from .utils import *
from .search import *

## Check if the browser is installed for selenium to use....
check_browser_installed()