import logging
import os

def setup_logger():
    # Check if logger already exists and has handlers to avoid duplicates
    logger = logging.getLogger('tedata')
    if logger.handlers:
        return logger
        
    logger.setLevel(logging.DEBUG)
    
    log_dir = os.path.join(os.path.dirname(__file__), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # File handler - captures DEBUG and above
    fh = logging.FileHandler(os.path.join(log_dir, 'tedata.log'))
    fh.setLevel(logging.DEBUG)
    
    # Console handler - captures INFO and above only
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_formatter = logging.Formatter('%(levelname)s - %(message)s')
    
    fh.setFormatter(file_formatter)
    ch.setFormatter(console_formatter)
    
    logger.addHandler(fh)
    logger.addHandler(ch)
    
    return logger