import sys
import platform
import requests
import subprocess
import os
from packaging import version
from log import logger
from config_json import __version__

APP_REPO = "https://api.github.com/repos/steelproxy/twitta/releases/latest"

def update_repo():  # Update code from GitHub
    """Run the update script to fetch the latest code from GitHub."""
        # determine if application is a script file or frozen exe
    if getattr(sys, 'frozen', False):
        try:

            # Get current executable path and version
            current_exe = sys.executable
            current_version = version.parse(__version__)
            system = platform.system().lower()
            
            # Get latest release from GitHub
            response = requests.get(APP_REPO)
            if response.status_code != 200:
                raise Exception("Failed to fetch release info")
                
            release_data = response.json()
            latest_version = version.parse(release_data['tag_name'].lstrip('v'))
            
            # Check if update is needed
            if latest_version <= current_version:
                logger.info(f"Already running latest version {current_version}")
                return
                
            # Find matching asset for current platform
            asset = None
            for a in release_data['assets']:
                if system in a['name'].lower():
                    asset = a
                    break
                    
            if not asset:
                raise Exception(f"No release found for {system}")
                
            # Download new version
            logger.info(f"Downloading update {latest_version}...")
            response = requests.get(asset['browser_download_url'], stream=True)
            
            # Save to temporary file
            import tempfile
            temp_path = tempfile.mktemp()
            with open(temp_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    
            # Replace current executable
            os.replace(temp_path, current_exe)

            logger.info("Update complete! Please restart the application.")
            
        except Exception as e:
            logger.error(f"Unexpected exception occured while updating: {e}")
            logger.info("Proceeding with current version...")
    else:
        try:
            subprocess.run(["git", "--version"], 
                        check=True, capture_output=True)  # Verify git installation
            subprocess.run(["git", "pull"], check=True)     # Pull latest changes
            logger.info("Repository updated successfully.")
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("Git not found in PATH. Skipping update...")
            logger.info("Proceeding with the current version...")
        except Exception as e:
            logger.error(f"Unexpected exception occured while updating: {e}")

# Handler for Ctrl+C (KeyboardInterrupt)
def _handle_exit(signum, frame):
    logger.info("Exiting program due to Ctrl+C...")
    sys.exit(0)
