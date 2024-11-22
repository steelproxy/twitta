import pytest
from flask import url_for
from web_server import TwitterBotServer, User
import json

@pytest.fixture
def test_config():
    return {
        'web_interface': {
            'secret_key': 'test_key',
            'port': 5000,
            'log_level': 'DEBUG',
            'credentials': {
                'admin': 'pbkdf2:sha256:test_hash'
            }
        },
        'accounts_to_reply': [],
        'twitter': {
            'bearer_token': 'test_token',
            'consumer_key': 'test_key',
            'consumer_secret': 'test_secret',
            'access_token': 'test_token',
            'access_token_secret': 'test_secret'
        },
        'openai': {
            'api_key': 'test_key'
        }
    }

@pytest.fixture
def app(test_config):
    server = TwitterBotServer(test_config, None)
    return server.app

@pytest.fixture
def client(app):
    return app.test_client()

def test_login_page(client):
    response = client.get('/login')
    assert response.status_code == 200
    assert b'Login to Twitta Bot' in response.data

def test_invalid_login(client):
    response = client.post('/login', data={
        'username': 'wrong',
        'password': 'wrong'
    })
    assert response.status_code == 200
    assert b'Invalid username or password' in response.data

def test_valid_login(client):
    response = client.post('/login', data={
        'username': 'admin',
        'password': 'correct_password'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Twitta Bot Dashboard' in response.data

def test_protected_routes_without_login(client):
    routes = ['/', '/accounts', '/api/status', '/api/logs']
    for route in routes:
        response = client.get(route)
        assert response.status_code == 302
        assert '/login' in response.location

def test_rate_limiting(client):
    for _ in range(6):
        response = client.post('/login', data={
            'username': 'wrong',
            'password': 'wrong'
        })
    assert response.status_code == 429 