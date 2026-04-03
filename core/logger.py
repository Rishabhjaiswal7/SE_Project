import logging
from logging.handlers import RotatingFileHandler

def setup_logger():
    logger = logging.getLogger("ztrace")
    logger.setLevel(logging.INFO)
    
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    
    fh = RotatingFileHandler("ztrace_backend.log", maxBytes=5*1024*1024, backupCount=2)
    fh.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    fh.setFormatter(formatter)

    logger.addHandler(ch)
    logger.addHandler(fh)
    return logger

log = setup_logger()
