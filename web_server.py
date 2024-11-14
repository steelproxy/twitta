from flask import Flask, jsonify, request, render_template
import threading
from datetime import datetime
import time
import x_api

PORT = 5000

class TwitterBotServer:
    def __init__(self, config, x_api_client):
        self.app = Flask(__name__)
        self.config = config
        self.client = x_api_client
        self.bot_thread = None
        self.setup_routes()
        
        # Bot state
        self.running = False
        self.start_time = None
        self.tweet_count = 0
        self.last_tweet = None
        self.error_count = 0
        self.status_message = ""

    def setup_routes(self):
        @self.app.route('/')
        def dashboard():
            return render_template('dashboard.html')

        @self.app.route('/api/start', methods=['POST'])
        def start_bot():
            if self.running:
                return jsonify({"status": "error", "message": "Bot is already running"}), 400
            
            self.bot_thread = threading.Thread(target=self._run_bot)
            self.bot_thread.daemon = True  # Make thread daemon so it stops when main program stops
            self.bot_thread.start()
            return jsonify({"status": "success", "message": "Bot started successfully"})

        @self.app.route('/api/stop', methods=['POST'])
        def stop_bot():
            if not self.running:
                return jsonify({"status": "error", "message": "Bot is not running"}), 400
            
            self.running = False
            self.status_message = "Bot is stopped"
            return jsonify({"status": "success", "message": "Bot stopped successfully"})

        @self.app.route('/api/status')
        def get_status():
            uptime = str(datetime.now() - self.start_time) if self.start_time else "Not started"
            last_tweet_ago = str(datetime.now() - self.last_tweet) if self.last_tweet else "Never"
            
            return jsonify({
                "running": self.running,
                "uptime": uptime,
                "tweet_count": self.tweet_count,
                "last_tweet": last_tweet_ago,
                "error_count": self.error_count,
                "status_message": self.status_message
            })

    def _run_bot(self):
        """Internal method to run the bot"""
        self.running = True
        self.start_time = datetime.now()
        self.status_message = "Bot is running"
        
        while self.running:
            try:
                x_api.reply_to_tweets(self.client, self.config, True)  # Run in auto mode
                self.tweet_count = x_api.tweet_count
                self.last_tweet = datetime.now()
            except Exception as e:
                self.error_count += 1
                self.status_message = f"Error: {str(e)}"
            time.sleep(60)  # Wait between cycles

    def start(self, host='0.0.0.0'):
        """Start the Flask server"""
        self.app.run(host=host, port=PORT, debug=False, use_reloader=False)

def create_server(config, x_api_client):
    """Factory function to create a new server instance"""
    return TwitterBotServer(config, x_api_client) 