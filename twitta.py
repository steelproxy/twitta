import config_json
import datetime
import openai
import random
import signal
from datetime import datetime
import time
import tweepy
import tweepy.errors
import utils
import x_api
from log import logger
from utils import __version__

def main():
    logger.info(f"Starting twitta {__version__}...")
    _setup_environment()
    
    config = config_json.load_config()
    logger.info(f"Configuration loaded.")
    
    x_api_client = _setup_api(config)
    logger.info(f"API initialized.")
    
    x_api.start_time = datetime.now()
    logger.info(f"Start time is: {x_api.start_time}")
    
    auto_reply = _interactive_prompt(config)

    while True:
        logger.info(f"Running in auto-reply mode: {str(auto_reply)}")
        x_api.reply_to_tweets(x_api_client, config, auto_reply)
        wait_time = random.randint(60, 300)
        logger.info(f"Waiting for {wait_time} seconds before the next tweet check.")
        time.sleep(wait_time)  # Random wait time

def _setup_environment():
    # Register the Ctrl+C handler
    signal.signal(signal.SIGINT, utils._handle_exit)
    
    # Start and update
    logger.info("Checking for updates...")
    utils.update_repo()
    
def _setup_api(config):
    try:
        client = tweepy.Client(
            bearer_token=config['twitter']['bearer_token'],
            consumer_key=config['twitter']['consumer_key'],
            consumer_secret=config['twitter']['consumer_secret'],
            access_token=config['twitter']['access_token'],
            access_token_secret=config['twitter']['access_token_secret']
        )
    except tweepy.errors.TweepyException as e:
        utils.fatal_error(f"Failed to initialize Twitter API client: {e}!")
    openai.api_key = config['openai']['api_key']
    return client

def _interactive_prompt(config):
    while True:
        command = input("Enter 'add' to add an account, 'run' to run, 'run-headless' to run without user input: ")
        if command == 'add':
            config_json.add_new_account(config)
        elif command in ['run', 'run-headless']:
            return command == 'run-headless'
        else:
            print("Invalid command.")
            

if __name__ == "__main__":
    main()