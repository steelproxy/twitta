import logging

logger = logging.getLogger()
__log_file__ = 'twitta.log'

# Only setup logging if no handlers exist
if not logger.handlers:
    logger.setLevel(logging.INFO)

    # Create a file handler
    file_handler = logging.FileHandler(__log_file__)
    file_handler.setLevel(logging.INFO)

    # Create a console handler for real-time logging
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # Create a formatter and set it for both handlers
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add the handlers to the logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)