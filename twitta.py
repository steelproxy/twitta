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

__version__ = "0.1"

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
                    "custom_prompt": {"type": "string"},
                },
                "required": ["username"],
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

def add_account(account, custom_prompt=None):
    account_info = {
        'username': account,
        'custom_prompt': custom_prompt if custom_prompt else "Reply to this tweet: {tweet_text}"
    }

    config['accounts_to_reply'].append(account_info)
    with open('config.json', 'w') as config_file:
        json.dump(config, config_file)

    logger.info(f"Added @{account} to reply list with prompt: {account_info['custom_prompt']}")

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
        custom_prompt = account_info['custom_prompt']

        try:
            user = client.get_user(username=account)
            if user.data:
                user_id = user.data.id
                tweets = client.get_users_tweets(user_id, max_results=10, tweet_fields=['created_at', 'text', 'attachments'])

                for tweet in tweets.data:
                    logger.info(f"Tweet read: {tweet.text}")
                    tweet_created_at = tweet.created_at.replace(tzinfo=None)

                    if tweet_created_at > start_time and tweet.id not in replied_tweet_ids:
                        try:
                            prompt = custom_prompt.format(tweet_text=tweet.text)
                            reply_text = get_chatgpt_response(prompt)
                            logger.info(f"ChatGPT Reply: {reply_text}")

                            # Ask to tweet
                            dry_run = input("Would you like to post this tweet? y/n: ")
                            if dry_run.lower() == "y":
                                client.create_tweet(text=f"@{account} {reply_text}", in_reply_to_tweet_id=tweet.id)
                                logger.info(f"Replied to @{account}: {reply_text}")

                            # Mark this tweet as replied
                            replied_tweet_ids.add(tweet.id)
                        except tweepy.TweepError as e:
                            logger.error(f"Tweepy error while replying to @{account}: {e}")
                        except Exception as e:
                            logger.error(f"General error while replying to @{account}: {e}")

            wait = random.randint(30, 63)
            logger.info(f"Waiting for {wait} seconds...")
            time.sleep(wait)  # Avoid hitting rate limits
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
            custom_prompt = input("Enter a custom reply prompt (leave blank for default): ")
            add_account(account, custom_prompt if custom_prompt else None)
        elif command == 'run':
            break
        else:
            print("Invalid command.")

if __name__ == "__main__":
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
