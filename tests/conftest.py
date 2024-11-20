import pytest
import os
import sys

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) 

@pytest.fixture(autouse=True)
def setup_test_logs():
    """Create test log directory and clean up after tests"""
    if not os.path.exists('logs'):
        os.makedirs('logs')
    yield
    # Clean up log files after tests
    for file in os.listdir('logs'):
        os.remove(os.path.join('logs', file)) 