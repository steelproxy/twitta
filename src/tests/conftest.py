import pytest
import os
import sys
import logging
import time

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) 

@pytest.fixture(autouse=True)
def setup_test_logs():
    """Create test log directory and clean up after tests"""
    if not os.path.exists('logs'):
        os.makedirs('logs')
    yield
    # Close all loggers before cleanup
    loggers = [logging.getLogger(name) for name in logging.root.manager.loggerDict]
    for logger in loggers:
        if hasattr(logger, 'handlers'):
            for handler in logger.handlers[:]:
                handler.close()
                logger.removeHandler(handler)
    
    # Clean up log files after tests
    for file in os.listdir('logs'):
        try:
            os.remove(os.path.join('logs', file))
        except PermissionError:
            # If still can't delete, wait a moment and try again
            time.sleep(0.1)
            try:
                os.remove(os.path.join('logs', file))
            except PermissionError:
                print(f"Warning: Could not delete {file}") 