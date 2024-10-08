import json
import tweepy
import openai
import logging
import time
import os
import random
from datetime import datetime

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

# Load configuration with error checking
def load_config():
    if not os.path.exists('config.json'):
        logger.warning("Configuration file not found. Creating a new one.")
        return create_config()
    
    with open('config.json') as config_file:
        config = json.load(config_file)

    required_keys = [
        'twitter', 'openai', 'accounts_to_reply', 'reply_prompt'
    ]
    for key in required_keys:
        if key not in config:
            logger.error(f"Missing required configuration key: {key}")
            raise KeyError(f"Missing required configuration key: {key}")

    # Check Twitter keys
    twitter_keys = ['bearer_token', 'consumer_key', 'consumer_secret', 'access_token', 'access_token_secret']
    for key in twitter_keys:
        if key not in config['twitter']:
            logger.error(f"Missing Twitter API key: {key}")
            raise KeyError(f"Missing Twitter API key: {key}")

    # Check OpenAI key
    if 'api_key' not in config['openai']:
        logger.error("Missing OpenAI API key.")
        raise KeyError("Missing OpenAI API key.")

    return config

def create_config():
    # Gather required information from the user
    twitter_config = {}
    twitter_config['bearer_token'] = input("Enter your Twitter Bearer Token: ")
    twitter_config['consumer_key'] = input("Enter your Twitter consumer key: ")
    twitter_config['consumer_secret'] = input("Enter your Twitter consumer secret: ")
    twitter_config['access_token'] = input("Enter your Twitter access token: ")
    twitter_config['access_token_secret'] = input("Enter your Twitter access token secret: ")

    openai_config = {}
    openai_config['api_key'] = input("Enter your OpenAI API key: ")

    accounts_to_reply = []
    reply_prompt = "Reply to this tweet: {tweet_text}"

    # Create the config dictionary
    config = {
        'twitter': twitter_config,
        'openai': openai_config,
        'accounts_to_reply': accounts_to_reply,
        'reply_prompt': reply_prompt
    }

    # Save the configuration to a file
    with open('config.json', 'w') as config_file:
        json.dump(config, config_file, indent=4)
    
    logger.info("New configuration file created.")
    return config

# Load the configuration
try:
    config = load_config()
except Exception as e:
    print(f"Configuration error: {e}")
    exit(1)

# Twitter API setup using v2
client = tweepy.Client(
    bearer_token=config['twitter']['bearer_token'],
    consumer_key=config['twitter']['consumer_key'],
    consumer_secret=config['twitter']['consumer_secret'],
    access_token=config['twitter']['access_token'],
    access_token_secret=config['twitter']['access_token_secret']
)

# OpenAI API setup
openai.api_key = config['openai']['api_key']

# Store the time when the bot starts
start_time = datetime.now()

# Store the IDs of tweets that have already been replied to
replied_tweet_ids = set()

def get_chatgpt_response(prompt):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return response['choices'][0]['message']['content']
    except Exception as e:
        logger.error(f"Error getting response from OpenAI: {e}")
        return "Sorry, I couldn't process that."

def reply_to_tweets():
    for account in config['accounts_to_reply']:
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
                            # Use the configured reply prompt
                            prompt = config['reply_prompt'].format(tweet_text=tweet.text)
                            reply_text = get_chatgpt_response(prompt)
                            # Uncomment the next line to enable tweeting
                            # client.create_tweet(text=f"@{account} {reply_text}", in_reply_to_tweet_id=tweet.id)
                            logger.info(f"Replied to @{account}: {reply_text}")

                            # Mark this tweet as replied
                            replied_tweet_ids.add(tweet.id)
                        except Exception as e:
                            logger.error(f"Error while replying to @{account}: {e}")

            wait = random.randint(30, 63)
            logger.info(f"Waiting for {wait} seconds...")
            time.sleep(wait)  # Avoid hitting rate limits
        except Exception as e:
            logger.error(f"General error while fetching tweets for @{account}: {e}")
            time.sleep(60)  # Wait before trying again in case of rate limit

def add_account(account):
    if account not in config['accounts_to_reply']:
        config['accounts_to_reply'].append(account)
        with open('config.json', 'w') as config_file:
            json.dump(config, config_file)
        logger.info(f"Added @{account} to reply list")
    else:
        logger.warning(f"Account @{account} is already in the reply list.")
        
def update_prompt(new_prompt):
    config['reply_prompt'] = new_prompt
    with open('config.json', 'w') as config_file:
        json.dump(config, config_file)
    logger.info(f"Updated reply prompt: {new_prompt}")

def interactive_prompt():
    while True:
        command = input("Enter 'add' to add an account, 'prompt' to update the reply prompt, 'run' to run: ")
        if command == 'add':
            account = input("Enter the Twitter account to reply to (without @): ")
            add_account(account)
        elif command == 'prompt':
            new_prompt = input("Enter the new reply prompt (use {tweet_text} to include tweet content): ")
            update_prompt(new_prompt)
        elif command == 'run':
            break
        else:
            print("Invalid command.")

if __name__ == "__main__":
    interactive_prompt()
    while True:
        reply_to_tweets()
        # Generate a random wait time between 5 to 15 minutes (300 to 900 seconds)
        wait_time = random.randint(60, 61)
        logger.info(f"Waiting for {wait_time} seconds before the next check.")
        time.sleep(wait_time)  # Random wait time
