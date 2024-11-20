import json
import os
import sys
import secrets
import jsonschema
from jsonschema import validate
from werkzeug.security import generate_password_hash
from log import app_logger as logger
from utils import __version__

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
                    "use_gpt": {"type": "boolean"},
                    "custom_prompt": {"type": "string"},
                    "predefined_replies": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                },
                "required": ["username", "use_gpt"],
            },
        },
        "web_interface": {
            "type": "object",
            "properties": {
                "credentials": {
                    "type": "object",
                    "additionalProperties": {"type": "string"}  # username: password_hash pairs
                },
                "secret_key": {"type": "string"},
                "port": {"type": "integer", "minimum": 1, "maximum": 65535},
                "log_level": {"type": "string", "enum": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]}
            },
            "required": ["credentials", "secret_key", "port", "log_level"]
        }
    },
    "required": ["version", "twitter", "openai", "accounts_to_reply", "web_interface"],
}

def setup_web_interface(config):
    """Set up web interface configuration"""
    if 'web_interface' not in config:
        logger.info("Setting up web interface configuration...")
        
        credentials = {}
        while True:
            username = input("Enter a new web interface username (or press enter to finish adding users): ").strip()
            if not username:
                if not credentials:
                    logger.warning("At least one user is required!")
                    continue
                break
                
            if username in credentials:
                logger.warning("Username already exists!")
                continue
                
            password = input(f"Enter password for {username}: ")
            if not password:
                logger.warning("Password cannot be empty!")
                continue
                
            credentials[username] = generate_password_hash(password)
            
            if input("Add another user? (y/n): ").lower() != 'y':
                break
        
        while True:
            port = input("Enter port number (default: 5000): ").strip()
            if not port:
                port = 5000
                break
            if port.isdigit() and 1 <= int(port) <= 65535:
                port = int(port)
                break
            logger.warning("Please enter a valid port number between 1 and 65535")
        
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        log_level = input(f"Enter log level ({'/'.join(valid_levels)}) (default: INFO): ").strip().upper()
        if log_level not in valid_levels:
            log_level = "INFO"
        
        config['web_interface'] = {
            'credentials': credentials,
            'secret_key': secrets.token_hex(32),
            'port': port,
            'log_level': log_level
        }
        _save_config(config)
        return True
    return False

def add_web_user(config):
    """Add a new web interface user"""
    if 'web_interface' not in config:
        setup_web_interface(config)
        return
        
    username = input("Enter new web interface username: ").strip()
    if not username:
        logger.warning("Username cannot be empty!")
        return False
        
    if username in config['web_interface']['credentials']:
        logger.warning(f"Unable to add user {username}! Username already exists.")
        return False
        
    password = input(f"Enter password for {username}: ")
    if not password:
        logger.warning("Password cannot be empty!")
        return False
        
    config['web_interface']['credentials'][username] = generate_password_hash(password)
    _save_config(config)
    logger.info(f"User {username} added successfully.")
    return True

def remove_web_user(config):
    """Remove a web interface user"""
    if 'web_interface' not in config or not config['web_interface']['credentials']:
        logger.warning("No web interface users configured!")
        return False
        
    print("\nExisting users:")
    for username in config['web_interface']['credentials'].keys():
        print(f"- {username}")
        
    username = input("\nEnter username to remove: ").strip()
    if username not in config['web_interface']['credentials']:
        logger.warning(f"User {username} does not exist!")
        return False
        
    if len(config['web_interface']['credentials']) == 1:
        logger.warning("Cannot remove last user! At least one user must remain.")
        return False
        
    del config['web_interface']['credentials'][username]
    _save_config(config)
    logger.info(f"User {username} removed successfully.")
    return True

def change_web_password(config):
    """Change password for a web interface user"""
    if 'web_interface' not in config or not config['web_interface']['credentials']:
        logger.warning("No web interface users configured!")
        return False
        
    print("\nExisting users:")
    for username in config['web_interface']['credentials'].keys():
        print(f"- {username}")
        
    username = input("\nEnter username to change password: ").strip()
    if username not in config['web_interface']['credentials']:
        logger.warning(f"User {username} does not exist!")
        return False
        
    password = input("Enter new password: ")
    if not password:
        logger.warning("Password cannot be empty!")
        return False
        
    config['web_interface']['credentials'][username] = generate_password_hash(password)
    _save_config(config)
    logger.info(f"Password changed successfully for user {username}.")
    return True

def regenerate_secret_key(config):
    """Regenerate the secret key for the web interface"""
    if 'web_interface' not in config:
        logger.warning("Web interface not configured!")
        return False
        
    config['web_interface']['secret_key'] = secrets.token_hex(32)
    _save_config(config)
    logger.info("Secret key regenerated successfully.")
    return True

# Load configuration with error checking
def load_config():
    if not os.path.exists(_get_config_path()):
        logger.warning("Configuration file not found. Creating a new one.")
        return _create_config()

    config = _load_config_json()

    if not _validate_config(config):
        logger.error("Configuration file is invalid. Creating a new one.")
        return _create_config()

    if config['version'] != __version__:
        logger.error(f"Configuration file version does not match twitta version [current version: {__version__}, config version: {config['version']}] recommend deleting config.json and restarting twitta!")

    return config

def _create_config():
    twitter_config = {key: input(f"Enter your Twitter {key.replace('_', ' ')}: ")
                      for key in ['bearer_token', 'consumer_key', 'consumer_secret', 'access_token', 'access_token_secret']}

    openai_config = {'api_key': input("Enter your OpenAI API key: ")}

    config = {
        'version': __version__,
        'twitter': twitter_config,
        'openai': openai_config,
        'accounts_to_reply': []
    }

    # Set up web interface during initial configuration
    setup_web_interface(config) # saves config anyways no need to call _save_config

    logger.info("New configuration file created.")
    return config

def add_new_account(config):
    new_account = input("Enter the Twitter account to reply to (without @): ")
    if any(account_info['username'] == new_account for account_info in config['accounts_to_reply']):
        logger.error(f"Unable to add user {new_account}! Account already exists in config.")
        return

    use_gpt = input("Use ChatGPT for replies? (y/n): ").strip().lower() == 'y'
    custom_prompt = input("Enter a custom reply prompt (leave blank for default) (use {tweet_text} as a placeholder for the tweet that ChatGPT is replying to.): ")
    
    predefined_replies = []
    while True:
        reply = input("Enter a predefined reply (press enter when finished adding replies): ")
        if not reply:
            break
        predefined_replies.append(reply.strip())
    
    _add_account(config, new_account, use_gpt, custom_prompt or None, predefined_replies)

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

def _load_config_json():
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
