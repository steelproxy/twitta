from flask import Flask, jsonify, request, render_template, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import threading
from datetime import datetime
import time
import x_api

PORT = 5000

class User(UserMixin):
    def __init__(self, username):
        self.id = username
        self.username = username

class TwitterBotServer:
    def __init__(self, config, x_api_client):
        self.app = Flask(__name__)
        self.app.secret_key = config['web_interface']['secret_key']  # dw not leaving this here
        self.config = config
        self.client = x_api_client
        self.bot_thread = None
        
        # Setup Flask-Login
        self.login_manager = LoginManager()
        self.login_manager.init_app(self.app)
        self.login_manager.login_view = 'login'
        self.login_manager.login_message = 'Please log in to access the dashboard.'
        
        self.setup_routes()
        
        # Bot state
        self.running = False
        self.start_time = None
        self.tweet_count = 0
        self.last_tweet = None
        self.error_count = 0
        self.status_message = ""

    def verify_credentials(self, username, password):
        stored_credentials = self.config['web_interface']['credentials']
        if username in stored_credentials:
            return check_password_hash(stored_credentials[username], password)
        return False

    def setup_routes(self):
        @self.login_manager.user_loader
        def load_user(username):
            if username in self.config['web_interface']['credentials']:
                return User(username)
            return None

        @self.app.route('/login', methods=['GET', 'POST'])
        def login():
            if current_user.is_authenticated:
                return redirect(url_for('dashboard'))
                
            if request.method == 'POST':
                username = request.form.get('username')
                password = request.form.get('password')
                
                if self.verify_credentials(username, password):
                    login_user(User(username))
                    next_page = request.args.get('next')
                    return redirect(next_page or url_for('dashboard'))
                flash('Invalid username or password')
            return render_template('login.html')

        @self.app.route('/logout')
        @login_required
        def logout():
            logout_user()
            return redirect(url_for('login'))

        @self.app.route('/')
        @login_required
        def dashboard():
            return render_template('dashboard.html')

        @self.app.route('/api/start', methods=['POST'])
        @login_required
        def start_bot():
            if self.running:
                return jsonify({"status": "error", "message": "Bot is already running"}), 400
            
            self.bot_thread = threading.Thread(target=self._run_bot)
            self.bot_thread.daemon = True
            self.bot_thread.start()
            return jsonify({"status": "success", "message": "Bot started successfully"})

        @self.app.route('/api/stop', methods=['POST'])
        @login_required
        def stop_bot():
            if not self.running:
                return jsonify({"status": "error", "message": "Bot is not running"}), 400
            
            self.running = False
            self.status_message = "Bot is stopped"
            return jsonify({"status": "success", "message": "Bot stopped successfully"})

        @self.app.route('/api/status')
        @login_required
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

    def start(self, host='0.0.0.0', port=5000):
        self.app.run(host=host, port=port, debug=False, use_reloader=False)

def create_server(config, x_api_client):
    """Factory function to create a new server instance"""
    return TwitterBotServer(config, x_api_client) 