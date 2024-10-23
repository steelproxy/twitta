import json
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

# Rate limits
APP_RATE_LIMIT = 300  # app limit: 300 requests per 15 min
USER_RATE_LIMIT = 900  # user limit: 900 requests per 15 min
USER_REPLY_LIMIT = 200  # user reply limit: 200 requests per 15 min

__version__ = "0.2.4"
__default_prompt__ = "Make sure not to include commentary or anything extra in your response, just raw text. Reply to this tweet: {tweet_text}"

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

# Load configuration with error checking
def load_config():
    if not os.path.exists('config.json'): # does not work with binary version
        logger.warning("Configuration file not found. Creating a new one.")
        return create_config()

    with open('config.json') as config_file:
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
    twitter_config = {
        'bearer_token': input("Enter your Twitter Bearer Token: "),
        'consumer_key': input("Enter your Twitter consumer key: "),
        'consumer_secret': input("Enter your Twitter consumer secret: "),
        'access_token': input("Enter your Twitter access token: "),
        'access_token_secret': input("Enter your Twitter access token secret: ")
    }

    openai_config = {
        'api_key': input("Enter your OpenAI API key: ")
    }

    config = {
        'version': __version__,
        'twitter': twitter_config,
        'openai': openai_config,
        'accounts_to_reply': [],  # Will be filled with account details
    }

    with open('config.json', 'w') as config_file:
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
    with open('config.json', 'w') as config_file:
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

def handle_reply(auto_reply, tweet, use_gpt, custom_prompt, predefined_replies):
    if use_gpt:
        prompt = custom_prompt.format(tweet_text=tweet.text)
        if not auto_reply:
            while True:
                reply_text = get_chatgpt_response(prompt)
                choice = input(f"Is this response ok? {reply_text} (y/n/e - will be regenerated if n - e will edit prompt for this run): ")
                if choice == "y":
                    return reply_text
                if choice == "e":
                    new_prompt = input("Enter a new prompt using {tweet_text} as a placeholder for the tweet: ")
                    prompt = new_prompt.format(tweet_text=tweet.text)
        return get_chatgpt_response(prompt)
    return random.choice(predefined_replies) if predefined_replies else ""


def reply_to_tweets(auto_reply):
    for account_info in config['accounts_to_reply']:
        account = account_info['username']
        use_gpt = account_info['use_gpt']
        custom_prompt = account_info['custom_prompt']
        predefined_replies = account_info['predefined_replies']
        
        try:
            # App rate limit (Application-only): 300 requests per 15-minute window shared among all users of your app
            # User rate limit (User context): 900 requests per 15-minute window per each authenticated user
            user = client.get_user(username=account)
    
            if user.data:
                user_id = user.data.id
                            
                # Increment the request count for fetching user
                increment_request_count(user_id)
                
                # Check if rate limited
                is_rate_limited(user_id)
                
                # App rate limit (Application-only): 1500 requests per 15-minute window shared among all users of your app
                # User rate limit (User context): 900 requests per 15-minute window per each authenticated user
                tweets = client.get_users_tweets(user_id, max_results=5, tweet_fields=['created_at', 'text', 'attachments'])
                
                # Increment the request count for fetching user
                increment_request_count(user_id)
                
                # Check if rate limited
                is_rate_limited(user_id)
                
                logger.info(f"Tweets fetched...")
                for tweet in tweets.data:
                    tweet_created_at = tweet.created_at.replace(tzinfo=None)

                    if tweet_created_at > start_time and tweet.id not in replied_tweet_ids:
                        try:
                            logger.info(f"Tweet replying to: {tweet.text}")

                            reply_text = handle_reply(auto_reply, tweet, use_gpt, custom_prompt, predefined_replies)
                            if reply_text != "":
                                if not auto_reply:
                                    choice = input(f"Would you like to post this tweet?: \"@{account} {reply_text}\" (y/n): ")
                                    if choice == "y":
                                        # Check if rate limited
                                        is_rate_limited(user_id)
                                        client.create_tweet(text=f"@{account} {reply_text}", in_reply_to_tweet_id=tweet.id, user_auth=True)
                                        increment_request_count(user_id)
                                        logger.info(f"Replied to @{account}: {reply_text}")
                                        wait = random.randint(30, 63)
                                        logger.info(f"Waiting for {wait} seconds till next reply...")
                                        time.sleep(wait)  # Avoid hitting rate limits
                                    else:
                                        logger.info(f"Skipping tweet...")
                                else:
                                    # Check if rate limited
                                    is_rate_limited(user_id)
                                    client.create_tweet(text=f"@{account} {reply_text}", in_reply_to_tweet_id=tweet.id, user_auth=True)
                                    increment_request_count(user_id)
                                    logger.info(f"Replied to @{account}: {reply_text}")
                                    wait = random.randint(30, 63)
                                    logger.info(f"Waiting for {wait} seconds till next reply...")
                                    time.sleep(wait)  # Avoid hitting rate limits
                            else:
                                logger.error(f"No predefined replies available and chatgpt either not working or not selected, unable to post tweet!")
                            # Mark this tweet as replied - might change this behavior to reflect choice
                            replied_tweet_ids.add(tweet.id)
                        except tweepy.errors.TweepyException as e:
                            logger.error(f"Tweepy error while replying to @{account}: {e}")
                        except Exception as e:
                            logger.error(f"General error while replying to @{account}: {e}")

        except tweepy.errors.TweepyException as e:
            message = str(e).replace('\n', ' ')
            logger.error(f"Tweepy error while fetching tweets for @{account}: \"{message}\" Waiting 60 seconds...")
            time.sleep(60)  # Wait before trying again in case of rate limit
        except Exception as e:
            message = str(e).replace('\n', ' ')
            logger.error(f"General error while fetching tweets for @{account}: \"{message}\" Waiting 60 seconds...")
            time.sleep(60)  # Wait before trying again

def interactive_prompt():
    while True:
        command = input("Enter 'add' to add an account, 'run' to run, 'run-headless' to run without user input: ")
        if command == 'add':
            new_account = input("Enter the Twitter account to reply to (without @): ")
            
            duplicate = False # probably not the cleanest way to do this
            for account_info in config['accounts_to_reply']:
                if new_account == account_info['username']:
                    logger.error(f"Unable to add user {new_account}! Account already exists in config.")
                    duplicate = True
                    break
            if duplicate:
                continue
            
            use_gpt = input("Use ChatGPT for replies? (y/n): ").strip().lower() == 'y'
            custom_prompt = input("Enter a custom reply prompt (leave blank for default) (use {tweet_text} as a placeholder for your tweet.): ")
            
            predefined_reply_prompt = "Enter a predefined reply you would like to add (press enter on empty prompt when finished adding replies): " # same with this
            predefined_replies = []
            predefined_reply = input(predefined_reply_prompt)
            while True:
                predefined_reply = input(predefined_reply_prompt)
                if predefined_reply != "":
                    predefined_replies += [predefined_reply.strip()]
                else:
                    break
            
            add_account(new_account, use_gpt, custom_prompt if custom_prompt else None, predefined_replies)
        elif command == 'run':
            return False
        elif command == 'run-headless':
            return True
        else:
            print("Invalid command.")

# Handler for Ctrl+C (KeyboardInterrupt)
def handle_exit(signum, frame):
    logger.info("Exiting program due to Ctrl+C...")
    sys.exit(0)

if __name__ == "__main__":
    # Register the Ctrl+C handler
    signal.signal(signal.SIGINT, handle_exit)
    
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
