import json
import os
import sys
import jsonschema
from jsonschema import validate
from log import logger

__version__ = "0.2.5"
__default_prompt__ = "Make sure not to include commentary or anything extra in your response, just raw text. Reply to this tweet: {tweet_text}"
__config_file__ = "config.json"

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
    if not os.path.exists(_get_config_path()): # does not work with binary version
        logger.warning("Configuration file not found. Creating a new one.")
        return create_config()

    config = _load_config()

    if not _validate_config(config):
        logger.error("Configuration file is invalid. Creating a new one.")
        return create_config()

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

    _save_config(config)

    logger.info("New configuration file created.")
    return config

def _add_account(config, account, use_gpt=True, custom_prompt=None, predefined_replies=None):
    account_info = {
        'username': account,
        'use_gpt': use_gpt,
        'custom_prompt': custom_prompt if custom_prompt else __default_prompt__,
        'predefined_replies': predefined_replies if predefined_replies else []
    }

    config['accounts_to_reply'].append(account_info)
    _save_config(config)

    logger.info(f"Added @{account} to reply list with gpt prompt: {account_info['custom_prompt']} and predefined replies: {account_info['predefined_replies']} [USING GPT {str(use_gpt)}]")

def _get_config_path():
    # determine if application is a script file or frozen exe
    if getattr(sys, 'frozen', False):
        application_path = os.path.dirname(sys.executable)
    elif __file__:
        application_path = os.path.dirname(__file__)

    return os.path.join(application_path, __config_file__)

def _load_config():
    with open(_get_config_path()) as config_file:
        return json.load(config_file)

def _save_config(config):
    config_path = _get_config_path()
    logger.info(f"Saving configuration to {config_path}")
    with open(config_path, 'w') as config_file:
        json.dump(config, config_file, indent=4)

def _validate_config(config):
    try:
        validate(instance=config, schema=config_schema)
    except jsonschema.ValidationError as e:
        logger.error(f"Configuration file is invalid: {e.message}")
        return False
    return True
