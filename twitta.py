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
from log import app_logger as logger
from utils import __version__
from web_server import create_server
import threading
import sys

def main():
    logger.info(f"Starting twitta {__version__}...")
    _setup_environment()
    
    config = config_json.load_config()
    logger.info(f"Configuration loaded.")
    
    x_api_client = _setup_api(config)
    logger.info(f"API initialized.")
    
    x_api.start_time = datetime.now()
    logger.info(f"Start time is: {x_api.start_time}")
    
    if '-d' in sys.argv:
        _run_daemon_mode(config, x_api_client)
    else:
        _handle_interactive_mode(config, x_api_client)
        
def _handle_interactive_mode(config, x_api_client):
    while True:
        print("\nAvailable commands:")
        print("1. add          - Add a new Twitter account to reply to")
        print("2. run          - Run the bot with manual approval") 
        print("3. run-headless - Run the bot automatically")
        print("4. daemon       - Start web interface")
        print("5. adduser      - Add web interface user")
        print("6. deluser      - Remove web interface user")
        print("7. passwd       - Change web interface password")
        print("8. newkey       - Regenerate web interface secret key")
        print("9. exit         - Exit the program")
        
        command = input("\nEnter command: ").strip().lower()
        
        if command == 'add':
            config_json.add_new_account(config)
        elif command in ['run', 'run-headless']:
            _run_normal_mode(config, x_api_client, command == 'run-headless')
        elif command == 'daemon':
            _run_daemon_mode(config, x_api_client)
        elif command == 'adduser':
            config_json.add_web_user(config)
        elif command == 'deluser':
            config_json.remove_web_user(config)
        elif command == 'passwd':
            config_json.change_web_password(config)
        elif command == 'newkey':
            config_json.regenerate_secret_key(config)
        elif command == 'exit':
            logger.info("Exiting program...")
            break
        else:
            print("Invalid command.")

def _run_normal_mode(config, x_api_client, auto_reply):
    logger.info(f"Running in auto-reply mode: {str(auto_reply)}")
    while True:
        x_api.reply_to_tweets(x_api_client, config, auto_reply)
        wait_time = random.randint(60, 300)
        logger.info(f"Waiting for {wait_time} seconds before the next tweet check.")
        time.sleep(wait_time)

def _run_daemon_mode(config, x_api_client):
    try:
        logger.info("Starting web interface...")
        try:
            server = create_server(config, x_api_client)
        except Exception as e:
            logger.error(f"Failed to create web server: {str(e)}! Shutting down web interface...")
            return
            
        # Start the web server in a separate thread
        server_thread = threading.Thread(target=server.start)
        server_thread.daemon = True
        
        try:
            server_thread.start()
        except RuntimeError as e:
            logger.error(f"Failed to start server thread: {str(e)}! Shutting down web interface...")
            return
            
        port = config['web_interface']['port']
        logger.info(f"Web interface available at http://localhost:{port}")
        
        # Keep the main thread alive and allow for command input
        while True:
            try:
                command = input("Enter 'stop' to shutdown the server: ")
                if command == 'stop':
                    logger.info("Shutting down web interface...")
                    break
            except (KeyboardInterrupt, EOFError):
                logger.info("Received shutdown signal... Shutting down web interface...")
                break
                
    except Exception as e:
        logger.error(f"Unexpected error in daemon mode: {str(e)}! Shutting down web interface...")
        return

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

if __name__ == "__main__":
    main()