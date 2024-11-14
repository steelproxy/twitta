from flask import Flask, jsonify, request, render_template, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import threading
from datetime import datetime
import time
import x_api
import os
import logging

PORT = 5000
__log_file__ = 'twitta_server.log'

class User(UserMixin):
    def __init__(self, username):
        self.id = username
        self.username = username

class TwitterBotServer:
    def __init__(self, config, x_api_client):
        self.app = Flask(__name__)
        
        # Configure Flask logging
        self.logger = logging.getLogger('flask_app')  # Create a dedicated logger for the Flask app
        self.logger.setLevel(logging.INFO)
        
        # Create file handler with matching format
        flask_file_handler = logging.FileHandler(__log_file__)
        flask_file_handler.setLevel(logging.INFO)
        
        # Use the same format as main logger
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        flask_file_handler.setFormatter(formatter)
        
        self.logger.addHandler(flask_file_handler)
        
        # Also configure werkzeug logging
        werkzeug_logger = logging.getLogger('werkzeug')
        werkzeug_logger.setLevel(logging.WARNING)
        werkzeug_logger.addHandler(flask_file_handler)
        
        self.app.secret_key = config['web_interface']['secret_key']  # dw not leaving this here
        self.config = config
        self.client = x_api_client
        self.bot_thread = None
        self.log_file = __log_file__
        self.server_start_time = x_api.start_time
        
        # Setup Flask-Login
        self.login_manager = LoginManager()
        self.login_manager.init_app(self.app)
        self.login_manager.login_view = 'login'
        self.login_manager.login_message = 'Please log in to access the dashboard.'
        
        # Add rate limiting
        self.ip_attempts = {}  # Track failed login attempts
        self.ip_requests = {}  # Track request frequency
        self.MAX_ATTEMPTS = 5  # Max failed logins before ban
        self.MAX_REQUESTS = 60  # Max requests per minute
        self.ATTEMPT_WINDOW = 300  # 5 minute window for failed logins
        self.REQUEST_WINDOW = 60  # 1 minute window for request rate
        
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

    def check_rate_limit(self, ip):
        """Check if IP is making too many requests"""
        current_time = time.time()
        
        # Clean old entries
        self.ip_requests = {
            ip_addr: (count, timestamp) 
            for ip_addr, (count, timestamp) in self.ip_requests.items()
            if current_time - timestamp < self.REQUEST_WINDOW
        }
        
        if ip not in self.ip_requests:
            self.ip_requests[ip] = (1, current_time)
            return True
            
        count, timestamp = self.ip_requests[ip]
        if current_time - timestamp >= self.REQUEST_WINDOW:
            # Reset counter for new window
            self.ip_requests[ip] = (1, current_time)
            return True
            
        if count >= self.MAX_REQUESTS:
            self.logger.warning(f"Authentication failed - Too many requests from {ip} [BANNED]")
            return False
            
        self.ip_requests[ip] = (count + 1, timestamp)
        return True

    def check_auth_attempts(self, ip):
        """Check if IP has too many failed login attempts"""
        current_time = time.time()
        
        # Clean old entries
        self.ip_attempts = {
            ip_addr: (attempts, timestamp) 
            for ip_addr, (attempts, timestamp) in self.ip_attempts.items()
            if current_time - timestamp < self.ATTEMPT_WINDOW
        }
        
        if ip not in self.ip_attempts:
            self.ip_attempts[ip] = (0, current_time)
            return True
            
        attempts, timestamp = self.ip_attempts[ip]
        if attempts >= self.MAX_ATTEMPTS:
            self.logger.warning(f"Authentication failed - Too many failed attempts from {ip} [BANNED]")
            return False
            
        return True

    def record_failed_attempt(self, ip):
        """Record a failed login attempt"""
        current_time = time.time()
        attempts, _ = self.ip_attempts.get(ip, (0, current_time))
        self.ip_attempts[ip] = (attempts + 1, current_time)

    def setup_routes(self):
        @self.login_manager.user_loader
        def load_user(username):
            if username in self.config['web_interface']['credentials']:
                return User(username)
            return None

        @self.app.before_request
        def check_request_limit():
            ip = request.remote_addr
            
            # Skip rate limiting for static files
            if request.path.startswith('/static/'):
                return
                
            if not self.check_rate_limit(ip):
                self.logger.warning(f"Rate limit exceeded - IP: {ip} [BANNED]")
                return "Rate limit exceeded", 429

        @self.app.route('/login', methods=['GET', 'POST'])
        def login():
            ip = request.remote_addr
            host = request.host
            
            if current_user.is_authenticated:
                self.logger.info(f"Already authenticated user accessed login page: {current_user.username} from {ip} ({host})")
                return redirect(url_for('dashboard'))
                
            if request.method == 'POST':
                if not self.check_auth_attempts(ip):
                    self.logger.warning(f"Authentication failed - IP blocked: {ip} ({host}) [BANNED]")
                    return "Too many failed attempts", 403
                    
                username = request.form.get('username')
                password = request.form.get('password')
                
                if self.verify_credentials(username, password):
                    login_user(User(username))
                    self.logger.info(f"Authentication successful - User: {username} from {ip} ({host})")
                    next_page = request.args.get('next')
                    return redirect(next_page or url_for('dashboard'))
                    
                self.record_failed_attempt(ip)
                self.logger.warning(f"Authentication failed - Invalid credentials from {ip} ({host}) for user: {username}")
                flash('Invalid username or password')
            return render_template('login.html')

        @self.app.route('/logout')
        @login_required
        def logout():
            if current_user.is_authenticated:
                username = current_user.username
                ip = request.remote_addr
                host = request.host
                logout_user()
                self.logger.info(f"User logged out: {username} from {ip} ({host})")
            return redirect(url_for('login'))

        @self.app.route('/')
        @login_required
        def dashboard():
            ip = request.remote_addr
            host = request.host
            self.logger.info(f"Dashboard accessed by user: {current_user.username} from {ip} ({host})")
            return render_template('dashboard.html')

        @self.app.route('/api/start', methods=['POST'])
        @login_required
        def start_bot():
            ip = request.remote_addr
            host = request.host
            
            if self.running:
                self.logger.warning(f"User {current_user.username} from {ip} ({host}) attempted to start already running bot")
                return jsonify({"status": "error", "message": "Bot is already running"}), 400
            
            self.logger.info(f"Bot started by user: {current_user.username} from {ip} ({host})")
            self.bot_thread = threading.Thread(target=self._run_bot)
            self.bot_thread.daemon = True
            self.bot_thread.start()
            return jsonify({"status": "success", "message": "Bot started successfully"})

        @self.app.route('/api/stop', methods=['POST'])
        @login_required
        def stop_bot():
            ip = request.remote_addr
            host = request.host
            
            if not self.running:
                self.logger.warning(f"User {current_user.username} from {ip} ({host}) attempted to stop inactive bot")
                return jsonify({"status": "error", "message": "Bot is not running"}), 400
            
            self.logger.info(f"Bot stopped by user: {current_user.username} from {ip} ({host})")
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
                "tweet_count": len(x_api.replied_tweet_ids),
                "last_tweet": last_tweet_ago,
                "error_count": self.error_count,
                "status_message": self.status_message
            })

        @self.app.route('/api/logs')
        @login_required
        def get_logs():
            try:
                with open(self.log_file, 'r') as f:
                    # Read all lines
                    all_lines = f.readlines()
                    
                    # Filter for lines after server start or last 100, whichever is less
                    recent_logs = []
                    for line in all_lines:
                        try:
                            # Parse timestamp from log line
                            timestamp_str = line.split(' - ')[0].strip()
                            # Remove microseconds for consistent parsing
                            timestamp_str = timestamp_str.split(',')[0]
                            log_time = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                            if log_time >= self.server_start_time:
                                recent_logs.append(line)
                        except (ValueError, IndexError):
                            # If we can't parse the timestamp, include the line anyway
                            recent_logs.append(line)
                    
                    # Take only the last 100 lines
                    logs = recent_logs[-100:]
                    return jsonify({"logs": logs})
            except FileNotFoundError:
                return jsonify({"logs": ["Log file not found"]})
            except Exception as e:
                return jsonify({"logs": [f"Error reading logs: {str(e)}"]})

    def _run_bot(self):
        """Internal method to run the bot"""
        self.running = True
        self.start_time = datetime.now()
        self.status_message = "Bot is running"
        
        while self.running:
            try:
                x_api.reply_to_tweets(self.client, self.config, True)  # Run in auto mode
                self.tweet_count = len(x_api.replied_tweet_ids)
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