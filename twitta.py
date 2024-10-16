import json
import openai
import tweepy
from openai import OpenAI
import logging
import time
import os
import random
from datetime import datetime
import jsonschema
from jsonschema import validate
import tweepy.errors
import signal
import sys

__version__ = "0.2.3"
__default_prompt__ = "Reply to this tweet: {tweet_text}"

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
    "required": ["twitter", "openai", "accounts_to_reply"],
}

# Load configuration with error checking
def load_config():
    if not os.path.exists('config.json'):
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

def reply_to_tweets():
    for account_info in config['accounts_to_reply']:
        account = account_info['username']
        use_gpt = account_info['use_gpt']
        custom_prompt = account_info['custom_prompt']
        predefined_replies = account_info['predefined_replies']
        
        try:
            user = client.get_user(username=account)
            if user.data:
                user_id = user.data.id
                tweets = client.get_users_tweets(user_id, max_results=5, tweet_fields=['created_at', 'text', 'attachments'])
                logger.info(f"Tweets read...")
                for tweet in tweets.data:
                    tweet_created_at = tweet.created_at.replace(tzinfo=None)

                    if tweet_created_at > start_time and tweet.id not in replied_tweet_ids:
                        try:
                            if use_gpt:
                                prompt = custom_prompt.format(tweet_text=tweet.text)
                                reply_text = get_chatgpt_response(prompt)
                            else:
                                reply_text = random.choice(predefined_replies) if predefined_replies else "No predefined replies available."

                            logger.info(f"Reply: {reply_text}")

                            choice = input(f"Would you like to post this tweet?: \"@{account} {reply_text}\" (y/n): ")
                            if choice == "y":
                                client.create_tweet(text=f"@{account} {reply_text}", in_reply_to_tweet_id=tweet.id, user_auth=True)
                                logger.info(f"Replied to @{account}: {reply_text}")
                                wait = random.randint(30, 63)
                                logger.info(f"Waiting for {wait} seconds till next reply...")
                                time.sleep(wait)  # Avoid hitting rate limits

                            # Mark this tweet as replied
                            replied_tweet_ids.add(tweet.id)
                        except tweepy.errors.TweepyException as e:
                            logger.error(f"Tweepy error while replying to @{account}: {e}")
                        except Exception as e:
                            logger.error(f"General error while replying to @{account}: {e}")

        except tweepy.errors.TweepyException as e:
            logger.error(f"Tweepy error while fetching tweets for @{account}: {e}. Waiting 60 seconds...")
            time.sleep(60)  # Wait before trying again in case of rate limit
        except Exception as e:
            logger.error(f"General error while fetching tweets for @{account}: {e}. Waiting 60 seconds...")
            time.sleep(60)  # Wait before trying again

def interactive_prompt():
    while True:
        command = input("Enter 'add' to add an account, 'run' to run: ")
        if command == 'add':
            account = input("Enter the Twitter account to reply to (without @): ")
            use_gpt = input("Use ChatGPT for replies? (y/n): ").strip().lower() == 'y'
            custom_prompt = input("Enter a custom reply prompt (leave blank for default): ")
            predefined_replies = input("Enter predefined replies separated by commas: ").split(',')
            predefined_replies = [reply.strip() for reply in predefined_replies if reply.strip()]  # Clean up whitespace
            add_account(account, use_gpt, custom_prompt if custom_prompt else None, predefined_replies)
        elif command == 'run':
            break
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
    
    interactive_prompt()

    while True:
        reply_to_tweets()
        wait_time = random.randint(60, 120)
        logger.info(f"Waiting for {wait_time} seconds before the next tweet check.")
        time.sleep(wait_time)  # Random wait time
