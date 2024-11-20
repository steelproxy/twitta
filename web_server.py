from flask import Flask, jsonify, request, render_template, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import threading
from datetime import datetime
import time
import x_api
import os
import logging
import json
from log import web_logger, api_logger
from collections import deque

class User(UserMixin):
    def __init__(self, username):
        self.id = username
        self.username = username

class TwitterBotServer:
    def __init__(self, config, x_api_client):
        self.app = Flask(__name__, static_folder='static')
        self._setup_logging(config)
        self._init_server(config, x_api_client)
        self._setup_auth()
        self._setup_rate_limits()
        self.setup_routes()

    def _setup_logging(self, config):
        """Configure logging for Flask and Werkzeug"""
        self.logger = web_logger
        self.api_logger = api_logger
        
        # Set log levels
        self.logger.setLevel(logging.getLevelName(config['web_interface']['log_level']))
        self.api_logger.setLevel(logging.getLevelName(config['web_interface']['log_level']))
        
        # Configure werkzeug logging
        werkzeug_logger = logging.getLogger('werkzeug')
        werkzeug_logger.setLevel(logging.WARNING)
        werkzeug_logger.handlers = []  # Clear existing handlers
        werkzeug_logger.addHandler(self.logger.handlers[0])  # Use same handler as web logger

    def _init_server(self, config, x_api_client):
        """Initialize server variables"""
        self.app.secret_key = config['web_interface']['secret_key']
        self.config = config
        self.client = x_api_client
        self.bot_thread = None
        self.server_start_time = x_api.start_time
        self.config_file_path = os.getenv('CONFIG_PATH', 'config.json')
        
        # Bot state
        self.running = False
        self.start_time = None
        self.tweet_count = 0
        self.last_tweet = None
        self.error_count = 0
        self.status_message = ""

    def _setup_auth(self):
        """Configure Flask-Login"""
        self.login_manager = LoginManager()
        self.login_manager.init_app(self.app)
        self.login_manager.login_view = 'login'
        self.login_manager.login_message = 'Please log in to access the dashboard.'

    def _setup_rate_limits(self):
        """Initialize rate limiting"""
        self.ip_attempts = {}
        self.ip_requests = {}
        self.MAX_ATTEMPTS = 5
        self.MAX_REQUESTS = 60
        self.ATTEMPT_WINDOW = 300
        self.REQUEST_WINDOW = 60

    def _verify_credentials(self, username, password):
        """Verify user credentials"""
        stored_credentials = self.config['web_interface']['credentials']
        if username in stored_credentials:
            return check_password_hash(stored_credentials[username], password)
        return False

    def _check_rate_limit(self, ip):
        """Check if IP is making too many requests"""
        current_time = time.time()
        self._clean_rate_limits(current_time)
        
        if ip not in self.ip_requests:
            self.ip_requests[ip] = (1, current_time)
            return True
            
        count, timestamp = self.ip_requests[ip]
        if current_time - timestamp >= self.REQUEST_WINDOW:
            self.ip_requests[ip] = (1, current_time)
            return True
            
        if count >= self.MAX_REQUESTS:
            self.logger.warning(f"Rate limit exceeded - IP: {ip} [BANNED]")
            return False
            
        self.ip_requests[ip] = (count + 1, timestamp)
        return True

    def _clean_rate_limits(self, current_time):
        """Clean expired rate limit entries"""
        self.ip_requests = {
            ip_addr: (count, timestamp) 
            for ip_addr, (count, timestamp) in self.ip_requests.items()
            if current_time - timestamp < self.REQUEST_WINDOW
        }

    def _check_auth_attempts(self, ip):
        """Check if IP has too many failed login attempts"""
        current_time = time.time()
        self._clean_auth_attempts(current_time)
        
        if ip not in self.ip_attempts:
            self.ip_attempts[ip] = (0, current_time)
            return True
            
        attempts, _ = self.ip_attempts[ip]
        if attempts >= self.MAX_ATTEMPTS:
            self.logger.warning(f"Authentication failed - Too many attempts from {ip} [BANNED]")
            return False
            
        return True

    def _clean_auth_attempts(self, current_time):
        """Clean expired authentication attempt entries"""
        self.ip_attempts = {
            ip_addr: (attempts, timestamp) 
            for ip_addr, (attempts, timestamp) in self.ip_attempts.items()
            if current_time - timestamp < self.ATTEMPT_WINDOW
        }

    def _record_failed_attempt(self, ip):
        """Record a failed login attempt"""
        current_time = time.time()
        attempts, _ = self.ip_attempts.get(ip, (0, current_time))
        self.ip_attempts[ip] = (attempts + 1, current_time)

    def _get_log_entries(self, log_file, max_lines=100):
        """Get recent log entries from specified file"""
        try:
            with open(log_file, 'r') as f:
                all_lines = f.readlines()
                recent_logs = []
                
                for line in all_lines:
                    try:
                        timestamp_str = line.split(' - ')[0].strip().split(',')[0]
                        log_time = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                        if log_time >= self.server_start_time:
                            recent_logs.append(line)
                    except (ValueError, IndexError):
                        recent_logs.append(line)
                
                return recent_logs[-max_lines:]
        except FileNotFoundError:
            return ["Log file not found"]
        except Exception as e:
            return [f"Error reading logs: {str(e)}"]

    def _run_bot(self):
        """Internal method to run the bot"""
        self.running = True
        self.start_time = datetime.now()
        self.status_message = "Bot is running"
        self.api_logger.info("Bot thread started")
        
        def update_status(message):
            self.status_message = message
            
        def update_tweet_count(count):
            self.tweet_count = count
            self.last_tweet = datetime.now()
            
        def handle_error(error_msg):
            self.error_count += 1
            self.status_message = f"Error: {error_msg}"
        
        # Register callbacks
        x_api.register_callbacks(
            status_update_callback=update_status,
            tweet_count_callback=update_tweet_count,
            error_callback=handle_error
        )
        
        while self.running:
            try:
                update_status("Running tweet reply cycle.")
                x_api.reply_to_tweets(self.client, self.config, True)
            except Exception as e:
                handle_error(str(e))
            update_status("Tweet reply cycle complete. Waiting 60 seconds before next cycle...")
            time.sleep(60)

    def setup_routes(self):
        """Set up all Flask routes"""
        self._setup_auth_routes()
        self._setup_api_routes()

    def _setup_auth_routes(self):
        """Set up authentication-related routes"""
        @self.login_manager.user_loader
        def load_user(username):
            if username in self.config['web_interface']['credentials']:
                return User(username)
            return None

        @self.app.before_request
        def check_request_limit():
            # Only check rate limits for login attempts
            if request.endpoint == 'login' and request.method == 'POST':
                ip = request.remote_addr
                if not self._check_rate_limit(ip):
                    self.logger.warning(f"Rate limit exceeded - IP: {ip} [BANNED]")
                    return "Rate limit exceeded", 429

        @self.app.route('/login', methods=['GET', 'POST'])
        def login():
            return self._handle_login()

        @self.app.route('/logout')
        @login_required
        def logout():
            return self._handle_logout()

    def _handle_login(self):
        """Handle login request"""
        ip = request.remote_addr
        host = request.host
        
        if current_user.is_authenticated:
            self.logger.info(f"Already authenticated user accessed login page: {current_user.username} from {ip} ({host})")
            return redirect(url_for('dashboard'))
            
        if request.method == 'POST':
            if not self._check_auth_attempts(ip):
                self.logger.warning(f"Authentication failed - IP blocked: {ip} ({host}) [BANNED]")
                return "Too many failed attempts", 429
                
            username = request.form.get('username')
            password = request.form.get('password')
            
            if self._verify_credentials(username, password):
                login_user(User(username))
                self.logger.info(f"Authentication successful - User: {username} from {ip} ({host})")
                next_page = request.args.get('next')
                return redirect(next_page or url_for('dashboard'))
                
            self._record_failed_attempt(ip)
            self.logger.warning(f"Authentication failed - Invalid credentials from {ip} ({host}) for user: {username}")
            flash('Invalid username or password')
        return render_template('login.html')

    def _handle_logout(self):
        """Handle logout request"""
        if current_user.is_authenticated:
            username = current_user.username
            ip = request.remote_addr
            host = request.host
            logout_user()
            self.logger.info(f"User logged out: {username} from {ip} ({host})")
        return redirect(url_for('login'))

    def _setup_api_routes(self):
        """Set up API endpoints"""
        @self.app.route('/')
        @login_required
        def dashboard():
            return self._handle_dashboard()

        @self.app.route('/api/start', methods=['POST'])
        @login_required
        def start_bot():
            return self._handle_start_bot()

        @self.app.route('/api/stop', methods=['POST'])
        @login_required
        def stop_bot():
            return self._handle_stop_bot()

        @self.app.route('/api/status')
        @login_required
        def get_status():
            return self._handle_get_status()

        @self.app.route('/api/logs')
        @login_required
        def get_logs():
            """Get log entries based on source"""
            source = request.args.get('source', 'web')
            if source == 'web':
                return self._handle_get_logs('logs/web.log')
            elif source == 'api':
                return self._handle_get_logs('logs/api.log')
            elif source == 'app':
                return self._handle_get_logs('logs/twitta.log', tail=False)  # Set tail=False to show all entries
            else:
                return jsonify({"logs": ["Invalid log source specified"]}), 400

        @self.app.route('/accounts', methods=['GET'])
        @login_required
        def manage_accounts():
            return self._handle_manage_accounts()

        @self.app.route('/api/accounts', methods=['GET', 'POST', 'DELETE'])
        @login_required
        def handle_accounts():
            if request.method == 'GET':
                return self._handle_get_accounts()
            elif request.method == 'POST':
                return self._handle_update_account()
            elif request.method == 'DELETE':
                return self._handle_delete_account()

    def _handle_dashboard(self):
        """Handle dashboard request"""
        ip = request.remote_addr
        host = request.host
        self.logger.info(f"Dashboard accessed by user: {current_user.username} from {ip} ({host})")
        return render_template('dashboard.html')

    def _handle_start_bot(self):
        """Handle bot start request"""
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

    def _handle_stop_bot(self):
        """Handle bot stop request"""
        ip = request.remote_addr
        host = request.host
        
        if not self.running:
            self.logger.warning(f"User {current_user.username} from {ip} ({host}) attempted to stop inactive bot")
            return jsonify({"status": "error", "message": "Bot is not running"}), 400
        
        self.logger.info(f"Bot stopped by user: {current_user.username} from {ip} ({host})")
        self.running = False
        self.status_message = "Bot has been stopped."
        return jsonify({"status": "success", "message": "Bot stopped successfully"})

    def _handle_get_status(self):
        """Handle status request"""
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

    def _handle_get_logs(self, log_file, tail=True):
        """Read log file contents"""
        try:
            if not os.path.exists(log_file):
                return jsonify({"logs": ["No log file found"]})
            
            with open(log_file, 'r') as f:
                if tail:
                    # Get last 100 lines for web and API logs
                    lines = deque(f, 100)
                else:
                    # Get all lines for application log
                    lines = f.readlines()
                
                # Clean up line endings consistently
                cleaned_lines = [line.rstrip('\n') for line in lines]
                return jsonify({"logs": cleaned_lines})
        except Exception as e:
            self.api_logger.error(f"Error reading log file: {str(e)}")
            return jsonify({"logs": ["Error reading log file"]})

    def _handle_manage_accounts(self):
        """Handle accounts page request"""
        ip = request.remote_addr
        host = request.host
        self.logger.info(f"Accounts page accessed by user: {current_user.username} from {ip} ({host})")
        return render_template('accounts.html')

    def _handle_get_accounts(self):
        """Return list of accounts to reply to"""
        return jsonify({
            "accounts": self.config['accounts_to_reply'],
            "running": self.running
        })

    def _handle_update_account(self):
        """Update or add account configuration"""
        data = request.json
        username = data.get('username', '').strip('@')
        if not username:
            return jsonify({"status": "error", "message": "Username is required"}), 400

        # Create new account object matching config structure
        new_account = {
            "username": username,
            "use_gpt": data.get('use_gpt', True),
            "custom_prompt": data.get('custom_prompt', ""),
            "predefined_replies": data.get('predefined_replies', [])
        }

        # Find and update existing account or add new one
        accounts = self.config['accounts_to_reply']
        for i, account in enumerate(accounts):
            if account['username'] == username:
                accounts[i] = new_account
                break
        else:
            accounts.append(new_account)

        self._save_config()
        return jsonify({
            "status": "success", 
            "message": "Account updated successfully",
            "restart_required": self.running
        })

    def _handle_delete_account(self):
        """Delete account from configuration"""
        username = request.json.get('username', '').strip('@')
        if not username:
            return jsonify({"status": "error", "message": "Username is required"}), 400

        accounts = self.config['accounts_to_reply']
        initial_length = len(accounts)
        self.config['accounts_to_reply'] = [acc for acc in accounts if acc['username'] != username]
        
        if len(self.config['accounts_to_reply']) == initial_length:
            return jsonify({"status": "error", "message": "Account not found"}), 404

        self._save_config()
        return jsonify({
            "status": "success", 
            "message": "Account deleted successfully",
            "restart_required": self.running
        })

    def _save_config(self):
        """Save current configuration to file"""
        try:
            with open(self.config_file_path, 'w') as f:
                json.dump(self.config, f, indent=4)
            self.logger.info("Configuration saved successfully")
        except Exception as e:
            self.logger.error(f"Error saving configuration: {str(e)}")
            raise

    def start(self, host='0.0.0.0'):
        """Start the Flask server"""
        self.app.run(
            host=host, 
            port=self.config['web_interface']['port'], 
            debug=False, 
            use_reloader=False
        )

def create_server(config, x_api_client):
    """Factory function to create a new server instance"""
    return TwitterBotServer(config, x_api_client) 