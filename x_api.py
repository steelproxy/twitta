import datetime
import gpt
import random
import time
import tweepy
import tweepy.errors
from datetime import timedelta
from datetime import datetime
from log import api_logger as logger

# Wait times
REPLY_WAIT_START = 60
REPLY_WAIT_END = 300

# Track request counts and timestamps
request_timestamps = []
user_request_counts = {}

# Track replies and start time
start_time = datetime.datetime.now(datetime.timezone.utc)
replied_tweet_ids = set()

# Add these callback functions at the top of the file
def register_callbacks(status_update_callback=None, tweet_count_callback=None, error_callback=None):
    global _status_update_callback, _tweet_count_callback, _error_callback
    _status_update_callback = status_update_callback
    _tweet_count_callback = tweet_count_callback
    _error_callback = error_callback

def _error_message(message):
    logger.error(message)
    if '_error_callback' in globals():
        _error_callback(message)

def _info_message(message):
    logger.info(message)
    if '_status_update_callback' in globals():
        _status_update_callback(message)

def _warning_message(message):
    logger.warning(message)
    if '_status_update_callback' in globals():
        _status_update_callback(message)

# Main function

def reply_to_tweets(client, config, auto_reply):
    for account in config['accounts_to_reply']:
        account_username = account['username']
        _info_message(f"Fetching tweets for @{account_username}...")
        try:
            user = client.get_user(username=account_username)
            if user.data:
                user_id = user.data.id
                tweets = client.get_users_tweets(user_id, max_results=5, start_time=start_time, tweet_fields=['created_at', 'text'])
                
                _info_message("Tweets fetched...")
                for tweet in tweets.data:
                    _process_tweet(client, tweet, account, user_id, auto_reply)
            else:
                _error_message(f"Fetched user contains no data! Account: {account_username}. Moving to next account...")
        except tweepy.errors.TweepyException as e:
            _error_message(f"Tweepy error while fetching tweets for @{account_username}: {str(e).replace('\n', ' ')} Waiting 60 seconds...")
            time.sleep(60)
        except Exception as e:
            _error_message(f"General error while fetching tweets for @{account_username}: {str(e).replace('\n', ' ')} Waiting 60 seconds...")
            time.sleep(60)

# Tweet processing

def _process_tweet(client, tweet, account, user_id, auto_reply):
    username = account['username']
    
    if tweet.id not in replied_tweet_ids:
        try:
            _info_message(f"Tweet replying to: {tweet.text}")
            reply_text = _handle_reply(account, tweet, auto_reply)
            if reply_text:
                _post_reply(client, username, tweet.id, user_id, reply_text, auto_reply)
            else:
                _error_message("No predefined replies available and chatgpt either not working or not selected, unable to post tweet!")
            replied_tweet_ids.add(tweet.id)
            if '_tweet_count_callback' in globals():
                _tweet_count_callback(len(replied_tweet_ids))
        except tweepy.errors.TooManyRequests as e:
            _error_message(f"Too many requests! Waiting 15 minutes...")
            time.sleep(15*60)
        except tweepy.errors.TweepyException as e:
            _error_message(f"Tweepy error while replying to @{account}: {e}")
        except Exception as e:
            _error_message(f"General error while replying to @{account}: {e}")

def _post_reply(client, username, tweet_id, user_id, reply_text, auto_reply):
    if not auto_reply:
        if input(f"Would you like to post this tweet?: \"@{username} {reply_text}\" (y/n): ") != 'y':
            logger.info("Skipping tweet...")
            return
    
    _info_message(f"Posting tweet: \"@{username} {reply_text}\"")
    try:
        client.create_tweet(text=f"@{username} {reply_text}", in_reply_to_tweet_id=tweet_id, user_auth=True)
    except tweepy.errors.TooManyRequests as e:
        _error_message(f"Too many requests! Waiting 15 minutes...")
        time.sleep(15*60)
    except tweepy.errors.TweepyException as e:
        _error_message(f"Tweepy error while posting reply: {e}")
    except Exception as e:
        _error_message(f"General error while posting reply: {e}")
    wait = random.randint(REPLY_WAIT_START, REPLY_WAIT_END)
    _info_message(f"Waiting for {wait} seconds till next reply...")
    time.sleep(wait)

# Interactive functions

def _get_user_approval(reply_text):
    while True:
        choice = input(f"Is this response ok? {reply_text} (y/n/e - will be regenerated if n - e will edit prompt for this run): ")
        if choice in ['y', 'n', 'e']:
            return choice
        else:
            return 'n'
        
def _handle_reply(account, tweet, auto_reply):
    use_gpt = account['use_gpt']
    custom_prompt = account['custom_prompt']
    predefined_replies = account['predefined_replies']
    
    if use_gpt:
        prompt = custom_prompt.format(tweet_text=tweet.text)
        while not auto_reply:
            reply_text = gpt.get_chatgpt_response(prompt)
            choice = _get_user_approval(reply_text)
            if choice == 'y':
                return reply_text
            if choice == 'e':
                prompt = input("Enter a new prompt using {tweet_text} as a placeholder for the tweet: ").format(tweet_text=tweet.text)
        return gpt.get_chatgpt_response(prompt)
    return random.choice(predefined_replies) if predefined_replies else ""
