import logging

def pytest_configure(config):
    # Set logging for the "httpx" module
    logging.getLogger("httpx").setLevel(logging.WARNING)