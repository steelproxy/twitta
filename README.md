# Twitta

Twitta is a Python script that automates replying to tweets using the OpenAI API and the Tweepy library. The bot reads tweets from specified Twitter accounts and generates replies based on a customizable prompt, making it a fun tool for engaging with your Twitter audience.

## Features

- **Automated Replies**: Automatically replies to tweets from specified accounts.
- **Custom Prompts**: Allows customization of reply prompts for each account.
- **Web Interface**: Control and monitor the bot through a web dashboard.
- **User Authentication**: Secure web interface with user authentication.
- **Rate Limiting**: Implements smart rate limiting to comply with Twitter's API limits.
- **Detailed Logging**: Comprehensive logging system with separate logs for web, API, and application events.
- **Auto Updates**: Built-in update checker and installer.
- **Multiple Operation Modes**:
  - Interactive mode with manual approval.
  - Headless mode for automated operation.
  - Daemon mode with web interface.
- **Smart Auto Updates**:
  - Automatically checks for and installs updates
  - Detects and installs new dependencies
  - Seamless version transitions

## Requirements

- Python 3.7+
- Required Python packages (installed automatically):
  - Flask and Flask-Login for web interface.
  - Tweepy for Twitter API integration.
  - OpenAI for GPT integration.
  - Additional dependencies in requirements.txt.

## Setup

1. Clone the repository:
```bash
git clone https://github.com/steelproxy/twitta.git
cd twitta
```

2. Run the setup script:

For Windows:
```bash
setup.bat
```

For macOS/Linux:
```bash
chmod +x setup.sh
./setup.sh
```

3. Create a configuration file [OPTIONAL]:
```json
{
    "twitter": {
        "bearer_token": "YOUR_TWITTER_BEARER_TOKEN",
        "consumer_key": "YOUR_TWITTER_CONSUMER_KEY",
        "consumer_secret": "YOUR_TWITTER_CONSUMER_SECRET",
        "access_token": "YOUR_TWITTER_ACCESS_TOKEN",
        "access_token_secret": "YOUR_TWITTER_ACCESS_TOKEN_SECRET"
    },
    "openai": {
        "api_key": "YOUR_OPENAI_API_KEY"
    },
    "web_interface": {
        "secret_key": "GENERATED_SECRET_KEY",
        "port": 5000,
        "log_level": "INFO",
        "credentials": {}
    },
    "accounts_to_reply": []
}
```

## Usage

### Command Line Interface
- `add` - Add a Twitter account to reply to
- `run` - Run the bot with manual approval
- `run-headless` - Run the bot automatically
- `daemon` - Start web interface
- `adduser` - Add web interface user
- `deluser` - Remove web interface user
- `passwd` - Change web interface password
- `newkey` - Regenerate web interface secret key
- `exit` - Exit the program

### Web Interface
Access the web interface at `http://localhost:5000` (default port) to:
- Monitor bot status
- View live logs
- Start/stop the bot
- Manage Twitter accounts
- View statistics

## Logging
Logs are stored in the `logs` directory:
- `twitta.log` - Main application logs
- `web.log` - Web interface logs
- `api.log` - Twitter API interaction logs

## License
This project is licensed under the MIT License. See the LICENSE file for details.

## Contributing
Contributions are welcome! Please feel free to submit a Pull Request.

## Contact
For questions or feedback, reach out at steelproxy@protonmail.com
