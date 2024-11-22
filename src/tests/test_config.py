import pytest
import json
import os
from config_json import _validate_config, _add_account

@pytest.fixture
def valid_config():
    return {
        "version": "0.2.5",
        "twitter": {
            "bearer_token": "test",
            "consumer_key": "test",
            "consumer_secret": "test",
            "access_token": "test",
            "access_token_secret": "test"
        },
        "openai": {
            "api_key": "test"
        },
        "accounts_to_reply": [],
        "web_interface": {
            "credentials": {},
            "secret_key": "test",
            "port": 5000,
            "log_level": "INFO"
        }
    }

def test_config_validation(valid_config):
    assert _validate_config(valid_config) == True

def test_add_account(valid_config):
    _add_account(valid_config, "test_user", True, "Test prompt", ["reply1"])
    account = valid_config['accounts_to_reply'][0]
    assert account['username'] == "test_user"
    assert account['use_gpt'] == True
    assert account['custom_prompt'] == "Test prompt"
    assert account['predefined_replies'] == ["reply1"] 