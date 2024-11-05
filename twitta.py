import json
import subprocess
import openai
from openai import OpenAI
import tweepy
import tweepy.errors
import logging
import time
import os
import random
from datetime import datetime, timedelta
import jsonschema
from jsonschema import validate
import signal
import sys
import requests
import platform
from packaging import version

APP_REPO = "https://api.github.com/repos/steelproxy/twitta/releases/latest"

# Rate limits
APP_RATE_LIMIT = 300  # app limit: 300 requests per 15 min
USER_RATE_LIMIT = 900  # user limit: 900 requests per 15 min
USER_REPLY_LIMIT = 200  # user reply limit: 200 requests per 15 min

__version__ = "0.2.5"
__default_prompt__ = "Make sure not to include commentary or anything extra in your response, just raw text. Reply to this tweet: {tweet_text}"
__config_file__ = "config.json"

# Track request counts and timestamps
request_timestamps = []
user_request_counts = {}
user_request_times = {}

# Setup logging for real-time output
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Create a file handler
file_handler = logging.FileHandler('twitta.log')
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

# Define the JSON schema
config_schema = {
    "type": "object",
    "properties": {
        "version": {
            "type": "string"
        },
        "twitter": {
            "type": "object",
            "properties": {
                "bearer_token": {"type": "string"},
                "consumer_key": {"type": "string"},
                "consumer_secret": {"type": "string"},
                "access_token": {"type": "string"},
                "access_token_secret": {"type": "string"},
            },
            "required": ["bearer_token", "consumer_key", "consumer_secret", "access_token", "access_token_secret"],
        },
        "openai": {
            "type": "object",
            "properties": {
                "api_key": {"type": "string"},
            },
            "required": ["api_key"],
        },
        "accounts_to_reply": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "username": {"type": "string"},
                    "use_gpt": {"type": "boolean"},  # Changed to use_gpt
                    "custom_prompt": {"type": "string"},
                    "predefined_replies": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                },
                "required": ["username", "use_gpt"],  # Added use_gpt to required fields
            },
        },
    },
    "required": ["version", "twitter", "openai", "accounts_to_reply"],
}

def _get_config_path():
    # determine if application is a script file or frozen exe
    if getattr(sys, 'frozen', False):
        application_path = os.path.dirname(sys.executable)
    elif __file__:
        application_path = os.path.dirname(__file__)

    return os.path.join(application_path, __config_file__)

# Load configuration with error checking
def load_config():
    if not os.path.exists(_get_config_path()): # does not work with binary version
        logger.warning("Configuration file not found. Creating a new one.")
        return create_config()

    with open(_get_config_path()) as config_file:
        config = json.load(config_file)

    # Validate the JSON structure
    try:
        validate(instance=config, schema=config_schema)
    except jsonschema.ValidationError as e:
        logger.error(f"Configuration file is invalid: {e.message}")
        raise

    if config['version'] != __version__:
        logger.error(f"Configuration file version does not match twitta version [current version: {__version__}, config version: {config['version']}] recommend deleting config.json and restarting twitta!")

    return config

def create_config():
    twitter_config = {key: input(f"Enter your Twitter {key.replace('_', ' ')}: ")
                      for key in ['bearer_token', 'consumer_key', 'consumer_secret', 'access_token', 'access_token_secret']}

    openai_config = {'api_key': input("Enter your OpenAI API key: ")}

    config = {
        'version': __version__,
        'twitter': twitter_config,
        'openai': openai_config,
        'accounts_to_reply': []
    }

    with open(_get_config_path(), 'w') as config_file:
        json.dump(config, config_file, indent=4)

    logger.info("New configuration file created.")
    return config

def add_account(account, use_gpt=True, custom_prompt=None, predefined_replies=None):
    account_info = {
        'username': account,
        'use_gpt': use_gpt,
        'custom_prompt': custom_prompt if custom_prompt else __default_prompt__,
        'predefined_replies': predefined_replies if predefined_replies else []
    }

    config['accounts_to_reply'].append(account_info)
    with open(_get_config_path(), 'w') as config_file:
        json.dump(config, config_file, indent=4)

    logger.info(f"Added @{account} to reply list with gpt prompt: {account_info['custom_prompt']} and predefined replies: {account_info['predefined_replies']} [USING GPT {str(use_gpt)}]")

def get_chatgpt_response(prompt):
    try:
        response = openai.chat.completions.create(model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}])
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Error getting response from OpenAI: {e}")
        return "Sorry, I couldn't process that."
    
def is_rate_limited(user_id):
    now = datetime.now()
    # Remove timestamps older than 15 minutes
    request_timestamps[:] = [ts for ts in request_timestamps if ts > now - timedelta(minutes=15)]
    
    # Count app requests
    if len(request_timestamps) >= APP_RATE_LIMIT:
        logger.warning("App rate limit reached. Waiting until reset...")
        wait_time = 15 * 60 - (now - request_timestamps[0]).total_seconds()
        time.sleep(max(0, wait_time))
    
    # Check user limits
    if user_id not in user_request_counts:
        user_request_counts[user_id] = {'count': 0, 'first_request_time': now}
    
    # Check if user limit is reached
    if user_request_counts[user_id]['count'] >= USER_RATE_LIMIT:
        logger.warning(f"User {user_id} rate limit reached. Waiting until reset...")
        wait_time = 15 * 60 - (now - user_request_counts[user_id]['first_request_time']).total_seconds()
        time.sleep(max(0, wait_time))
        user_request_counts[user_id]['count'] = 0  # Reset after waiting
        user_request_counts[user_id]['first_request_time'] = now
    
    return user_request_counts[user_id]

def increment_request_count(user_id):
    user_request_counts[user_id]['count'] += 1
    request_timestamps.append(datetime.now())

def get_user_approval(reply_text):
    while True:
        choice = input(f"Is this response ok? {reply_text} (y/n/e - will be regenerated if n - e will edit prompt for this run): ")
        if choice in ['y', 'n', 'e']:
            return choice
    
def handle_reply(auto_reply, tweet, use_gpt, custom_prompt, predefined_replies):
    if use_gpt:
        prompt = custom_prompt.format(tweet_text=tweet.text)
        while not auto_reply:
            reply_text = get_chatgpt_response(prompt)
            choice = get_user_approval(reply_text)
            if choice == 'y':
                return reply_text
            if choice == 'e':
                prompt = input("Enter a new prompt using {tweet_text} as a placeholder for the tweet: ").format(tweet_text=tweet.text)
        return get_chatgpt_response(prompt)
    return random.choice(predefined_replies) if predefined_replies else ""

def process_tweet(tweet, account, use_gpt, custom_prompt, predefined_replies, auto_reply, user_id):
    if tweet.created_at.replace(tzinfo=None) > start_time and tweet.id not in replied_tweet_ids:
        try:
            logger.info(f"Tweet replying to: {tweet.text}")
            reply_text = handle_reply(auto_reply, tweet, use_gpt, custom_prompt, predefined_replies)
            if reply_text:
                post_reply(reply_text, account, tweet.id, user_id, auto_reply)
            else:
                logger.error("No predefined replies available and chatgpt either not working or not selected, unable to post tweet!")
            replied_tweet_ids.add(tweet.id)
        except tweepy.errors.TweepyException as e:
            logger.error(f"Tweepy error while replying to @{account}: {e}")
        except Exception as e:
            logger.error(f"General error while replying to @{account}: {e}")

def post_reply(reply_text, account, tweet_id, user_id, auto_reply):
    if not auto_reply:
        if input(f"Would you like to post this tweet?: \"@{account} {reply_text}\" (y/n): ") != 'y':
            logger.info("Skipping tweet...")
            return
    
    is_rate_limited(user_id)
    client.create_tweet(text=f"@{account} {reply_text}", in_reply_to_tweet_id=tweet_id, user_auth=True)
    increment_request_count(user_id) # for client.create_tweet
    logger.info(f"Replied to @{account}: {reply_text}")
    wait = random.randint(30, 63)
    logger.info(f"Waiting for {wait} seconds till next reply...")
    time.sleep(wait)

def reply_to_tweets(auto_reply):
    for account_info in config['accounts_to_reply']:
        account = account_info['username']
        try:
            user = client.get_user(username=account)
            if user.data:
                user_id = user.data.id
                increment_request_count(user_id) # for client.get_user
                is_rate_limited(user_id)
                
                tweets = client.get_users_tweets(user_id, max_results=5, tweet_fields=['created_at', 'text', 'attachments'])
                increment_request_count(user_id) # for client.get_users_tweets
                is_rate_limited(user_id)
                
                logger.info("Tweets fetched...")
                for tweet in tweets.data:
                    process_tweet(tweet, account, account_info['use_gpt'], account_info['custom_prompt'], 
                                  account_info['predefined_replies'], auto_reply, user_id)
        except tweepy.errors.TweepyException as e:
            logger.error(f"Tweepy error while fetching tweets for @{account}: {str(e).replace('\n', ' ')} Waiting 60 seconds...")
            time.sleep(60)
        except Exception as e:
            logger.error(f"General error while fetching tweets for @{account}: {str(e).replace('\n', ' ')} Waiting 60 seconds...")
            time.sleep(60)

def add_new_account():
    new_account = input("Enter the Twitter account to reply to (without @): ")
    if any(account_info['username'] == new_account for account_info in config['accounts_to_reply']):
        logger.error(f"Unable to add user {new_account}! Account already exists in config.")
        return

    use_gpt = input("Use ChatGPT for replies? (y/n): ").strip().lower() == 'y'
    custom_prompt = input("Enter a custom reply prompt (leave blank for default) (use {tweet_text} as a placeholder for your tweet.): ")
    
    predefined_replies = []
    while True:
        reply = input("Enter a predefined reply (press enter when finished adding replies): ")
        if not reply:
            break
        predefined_replies.append(reply.strip())
    
    add_account(new_account, use_gpt, custom_prompt or None, predefined_replies)

def interactive_prompt():
    while True:
        command = input("Enter 'add' to add an account, 'run' to run, 'run-headless' to run without user input: ")
        if command == 'add':
            add_new_account()
        elif command in ['run', 'run-headless']:
            return command == 'run-headless'
        else:
            print("Invalid command.")

def update_repo():  # Update code from GitHub
    """Run the update script to fetch the latest code from GitHub."""
        # determine if application is a script file or frozen exe
    if getattr(sys, 'frozen', False):
        try:

            # Get current executable path and version
            current_exe = sys.executable
            current_version = version.parse(__version__)
            system = platform.system().lower()
            
            # Get latest release from GitHub
            response = requests.get(APP_REPO)
            if response.status_code != 200:
                raise Exception("Failed to fetch release info")
                
            release_data = response.json()
            latest_version = version.parse(release_data['tag_name'].lstrip('v'))
            
            # Check if update is needed
            if latest_version <= current_version:
                logger.info(f"Already running latest version {current_version}")
                return
                
            # Find matching asset for current platform
            asset = None
            for a in release_data['assets']:
                if system in a['name'].lower():
                    asset = a
                    break
                    
            if not asset:
                raise Exception(f"No release found for {system}")
                
            # Download new version
            logging.info(f"Downloading update {latest_version}...")
            response = requests.get(asset['browser_download_url'], stream=True)
            
            # Save to temporary file
            import tempfile
            temp_path = tempfile.mktemp()
            with open(temp_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    
            # Replace current executable
            os.replace(temp_path, current_exe)
            logger.info("Update complete! Please restart the application.")
            
        except Exception as e:
            logger.error(f"Unexpected exception occured while updating: {e}")
            logger.info("Proceeding with current version...")
    else:
        try:
            subprocess.run(["git", "--version"], 
                        check=True, capture_output=True)  # Verify git installation
            subprocess.run(["git", "pull"], check=True)     # Pull latest changes
            logger.info("Repository updated successfully.")
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("Git not found in PATH. Skipping update...")
            logger.info("Proceeding with the current version...")
        except Exception as e:
            logger.error(f"Unexpected exception occured while updating: {e}")
            

# Handler for Ctrl+C (KeyboardInterrupt)
def handle_exit(signum, frame):
    logger.info("Exiting program due to Ctrl+C...")
    sys.exit(0)

if __name__ == "__main__":
    # Register the Ctrl+C handler
    signal.signal(signal.SIGINT, handle_exit)
    
    logger.info("Checking for updates...")
    update_repo()
    
    logger.info(f"Starting twitta {__version__}...")
    config = load_config()
    logger.info(f"Configuration loaded.")
    client = tweepy.Client(
        bearer_token=config['twitter']['bearer_token'],
        consumer_key=config['twitter']['consumer_key'],
        consumer_secret=config['twitter']['consumer_secret'],
        access_token=config['twitter']['access_token'],
        access_token_secret=config['twitter']['access_token_secret']
    )
    openai.api_key = config['openai']['api_key']

    start_time = datetime.now()
    logger.info(f"Start time is: {start_time}")
    replied_tweet_ids = set()
    
    auto_reply = interactive_prompt()

    while True:
        logger.info(f"Running in auto-reply mode: {str(auto_reply)}")
        reply_to_tweets(auto_reply)
        wait_time = random.randint(60, 120)
        logger.info(f"Waiting for {wait_time} seconds before the next tweet check.")
        time.sleep(wait_time)  # Random wait time
