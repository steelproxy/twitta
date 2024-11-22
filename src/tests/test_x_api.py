import pytest
from x_api import _handle_reply, _increment_request_count
from datetime import datetime
import tweepy

@pytest.fixture
def mock_tweet():
    class MockTweet:
        def __init__(self):
            self.text = "Test tweet"
    return MockTweet()

@pytest.fixture
def mock_account():
    return {
        'username': 'test_user',
        'use_gpt': True,
        'custom_prompt': 'Reply to: {tweet_text}',
        'predefined_replies': ['Reply 1', 'Reply 2']
    }

def test_handle_reply_with_gpt(mock_account, mock_tweet, monkeypatch):
    def mock_gpt_response(*args):
        return "GPT generated reply"
    
    monkeypatch.setattr('gpt.get_chatgpt_response', mock_gpt_response)
    reply = _handle_reply(mock_account, mock_tweet, True)
    assert reply == "GPT generated reply"

def test_handle_reply_with_predefined(mock_account, mock_tweet):
    mock_account['use_gpt'] = False
    reply = _handle_reply(mock_account, mock_tweet, True)
    assert reply in mock_account['predefined_replies']

def test_rate_limiting():
    user_id = "test_user"
    _increment_request_count(user_id)
    from x_api import user_request_counts
    
    assert user_id in user_request_counts
    assert user_request_counts[user_id]['count'] == 1
    assert isinstance(user_request_counts[user_id]['first_request_time'], datetime) 