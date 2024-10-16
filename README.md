# Twitta

Twitta is a Python script that automates replying to tweets using the OpenAI API and the Tweepy library. The bot reads tweets from specified Twitter accounts and generates replies based on a customizable prompt, making it a fun tool for engaging with your Twitter audience.

## Features

- **Automated Replies**: Automatically replies to tweets from specified accounts.
- **Custom Prompts**: Allows customization of reply prompts for each account.
- **Logging**: Detailed logging of actions and errors, saved to a log file (`twitta.log`).
- **Configuration Management**: Loads Twitter and OpenAI API credentials from a JSON configuration file.
- **Rate Limiting**: Implements random wait times to avoid exceeding Twitter’s API limits.

## Requirements

- Python 3.7+
- `tweepy` library
- `openai` library
- `jsonschema` library

You can install the required libraries using pip:

```bash
pip install tweepy openai jsonschema
```

## Setup
1. Clone the repository:
```bash
git clone https://github.com/yourusername/twitta.git
cd twitta
```
2. Create a configuration file:

- If you don’t have a config.json file, the script will prompt you to create one on the first run. Alternatively, create it manually in the following format:

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
    "accounts_to_reply": []
}
```
3. Run the script:
- Execute the script using Python:

```bash
chmod +x ./twitta.py
python twitta.py
```

4. Interactively add accounts:

- Once the script is running, you can add Twitter accounts to reply to and start the bot by following the on-screen prompts.

## Using the Binary
For those who prefer not to run the script manually, you can download the latest binary from the Releases page.

## Steps to Use the Binary:
1. Download the latest release: Choose the appropriate binary for your operating system from the Releases page.

2. Extract the files: If the binary is in a compressed format, extract it to your desired location.

3. Configure the JSON file: Ensure you have a config.json file set up as described in the "Setup" section.

4. Run the binary: Execute the binary directly.
- On macOS/Linux enter your shell of choice and run:
```bash
chmod +x ./twitta
./twitta
```
- On Windows simply double click the executable
  
## Usage
- Enter 'add' to add a Twitter account to the reply list.
- Enter 'run' to start the bot, which will begin monitoring the specified accounts for tweets.

## Logging
All logs will be written to twitta.log in the same directory. You can check this file for detailed information about the bot's activities and any errors that occur.

## License
This project is licensed under the MIT License. See the LICENSE file for more information.

## Contributing
Contributions are welcome! If you have suggestions for improvements or find a bug, please create an issue or submit a pull request.

# Contact
For questions or feedback, feel free to reach out at steelproxy@protonmail.com
