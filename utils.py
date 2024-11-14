import sys
import platform
import requests
import subprocess
import os
from packaging import version
from log import logger
from config_json import __version__

__version__ = "0.2.5"
APP_REPO = "https://api.github.com/repos/steelproxy/twitta/releases/latest"

def update_repo():  # Update code from GitHub
    """Run the update script to fetch the latest code from GitHub."""
    
    # Determine if application is a script file or frozen exe
    if getattr(sys, 'frozen', False):
        # Get current executable path and version
        current_exe = sys.executable
        current_version = version.parse(__version__)
        system_platform = platform.system().lower()
        
        # Get latest release from GitHub
        response = requests.get(APP_REPO)
        if response.status_code != 200:
            raise Exception("Failed to fetch release info")
        
        release_data = response.json()
        latest_version = version.parse(release_data['tag_name'].lstrip('v'))
        
        # Check if update is needed
        if latest_version <= current_version:
            logger.info(f"Already running latest version of ednasg: {current_version}")
            return
        
        # Find matching asset for current platform
        asset = None
        for a in release_data['assets']:
            if system_platform in a['name'].lower():
                asset = a
                break
        
        if not asset:
            logger.error(f"No release was found for platform: {system_platform}! Skipping update...")
            return
        
        # Download new version
        logger.info(f"Downloading update {latest_version}...")
        try:
            response = requests.get(asset['browser_download_url'], stream=True)
            if response.status_code != 200:
                logger.error(f"Failed to download update! Response code: {response.status_code}. Skipping update...")
                return
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to download update! Exception occurred: {e}. Skipping update...")
            return
        
        try:
            # Save to temporary file
            import tempfile
            temp_dir = tempfile.mkdtemp()
            temp_path = os.path.join(temp_dir, 'update.exe')

            with open(temp_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            if os.system == "nt":
                _replace_binary(temp_dir, temp_path, current_exe)
            else:
                os.replace(temp_path, current_exe)
        except Exception as e:
            logger.error(f"Failed to download update! Exception occurred: {e}. Skipping update...")
            return

        logger.info("Update complete! Please restart the application.")
    else:
        try:
            subprocess.run(["git", "--version"], 
                        check=True, capture_output=True)  # Verify git installation
            subprocess.run(["git", "pull"], check=True)     # Pull latest changes
            logger.info("Repository updated successfully.")
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("Git not found in PATH. Skipping update...")
        except Exception as e:
           logger.error(f"Failed to download update! Exception occurred: {e}. Skipping update...")

def _replace_binary(temp_dir, temp_path, current_exe):
    # Create batch script to replace exe after this process exits
    batch_path = os.path.join(temp_dir, 'update.bat')
    with open(batch_path, 'w') as f:
        f.write('@echo off\n')
        f.write(':wait\n')
        f.write(f'tasklist | find /i "{os.path.basename(current_exe)}" >nul\n')
        f.write('if errorlevel 1 (\n')
        f.write(f'  move /y "{temp_path}" "{current_exe}"\n')
        f.write('  rmdir /s /q "%~dp0"\n')
        f.write('  exit\n')
        f.write(') else (\n')
        f.write('  timeout /t 1 /nobreak >nul\n')
        f.write('  goto wait\n')
        f.write(')\n')

    # Launch updater script and exit
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    subprocess.Popen(['cmd', '/c', batch_path],
                     startupinfo=startupinfo,
                     creationflags=subprocess.CREATE_NEW_CONSOLE)

# Handler for Ctrl+C (KeyboardInterrupt)
def _handle_exit(signum, frame):
    logger.info("Exiting program due to Ctrl+C...")
    sys.exit(0)
