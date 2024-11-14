import openai
from openai import OpenAI
import tweepy
import tweepy.errors
import time
import random
from datetime import datetime, timedelta
import signal
from log import logger
import config_json
import utils
from utils import __version__

# Rate limits
APP_RATE_LIMIT = 300  # app limit: 300 requests per 15 min
USER_RATE_LIMIT = 900  # user limit: 900 requests per 15 min
USER_REPLY_LIMIT = 200  # user reply limit: 200 requests per 15 min

# Track request counts and timestamps
request_timestamps = []
user_request_counts = {}
user_request_times = {}

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

def process_tweet(tweet, account, use_gpt, custom_prompt, predefined_replies, auto_reply, user_id,):
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

def add_new_account(config):
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
    
    config_json._add_account(config, new_account, use_gpt, custom_prompt or None, predefined_replies)

def interactive_prompt(config):
    while True:
        command = input("Enter 'add' to add an account, 'run' to run, 'run-headless' to run without user input: ")
        if command == 'add':
            add_new_account(config)
        elif command in ['run', 'run-headless']:
            return command == 'run-headless'
        else:
            print("Invalid command.")
            
def main():
    # Register the Ctrl+C handler
    signal.signal(signal.SIGINT, utils._handle_exit)
    
    # Start and update
    logger.info(f"Starting twitta {__version__}...")
    logger.info("Checking for updates...")
    utils.update_repo()

    config = config_json.load_config()
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
    
    auto_reply = interactive_prompt(config)

    while True:
        logger.info(f"Running in auto-reply mode: {str(auto_reply)}")
        reply_to_tweets(auto_reply)
        wait_time = random.randint(60, 120)
        logger.info(f"Waiting for {wait_time} seconds before the next tweet check.")
        time.sleep(wait_time)  # Random wait time


if __name__ == "__main__":
    main()