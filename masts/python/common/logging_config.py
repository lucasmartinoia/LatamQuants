import logging

def setup_logging():
    logging.basicConfig(filename='../smart_trader.log', level=logging.DEBUG, format='%(asctime)s [%(levelname)s] %(funcName)s line %(lineno)d: %(message)s')

# Create a logger object
logger = logging.getLogger(__name__)
