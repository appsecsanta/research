import requests
import os
import sys
import shutil
import subprocess
import tempfile
import logging
import json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def auto_update(current_version: str, check_url: str, download_url_template: str, current_exe: str) -> bool:
    """
    Checks for updates, downloads if available, and applies the update.
    
    :param current_version: Current version of the application (e.g., '1.0.0')
    :param check_url: URL to check for the latest version (expects JSON with 'latest_version' and 'download_url')
    :param download_url_template: Template for download URL if not provided in check response
    :param current_exe: Path to the current executable
    :return: True if update was applied (application will restart), False otherwise
    """
    try:
        # Check for latest version
        response = requests.get(check_url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        latest_version = data.get('latest_version')
        if not latest_version:
            raise ValueError("Invalid response: 'latest_version' not found")
        
        # Compare versions (assuming semantic versioning)
        if not _is_newer_version(latest_version, current_version):
            logging.info("Application is up to date.")
            return False
        
        # Get download URL
        download_url = data.get('download_url', download_url_template.format(version=latest_version))
        
        # Download update to temp file
        temp_dir = tempfile.mkdtemp()
        update_file = os.path.join(temp_dir, os.path.basename(current_exe))
        
        logging.info(f"Downloading update from {download_url} to {update_file}")
        with requests.get(download_url, stream=True, timeout=30) as resp:
            resp.raise_for_status()
            with open(update_file, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
        
        # Make executable
        os.chmod(update_file, 0o755)
        
        # Apply update based on platform
        logging.info("Applying update...")
        if sys.platform == 'win32':
            _apply_update_windows(update_file, current_exe)
        else:
            _apply_update_unix(update_file, current_exe)
        
        return True
    
    except requests.RequestException as e:
        logging.error(f"Network error during update: {e}")
    except json.JSONDecodeError as e:
        logging.error(f"Invalid JSON response: {e}")
    except Exception as e:
        logging.error(f"Unexpected error during update: {e}")
    
    return False

def _is_newer_version(latest: str, current: str) -> bool:
    """Compare two semantic versions."""
    latest_parts = list(map(int, latest.split('.')))
    current_parts = list(map(int, current.split('.')))
    return latest_parts > current_parts

def _apply_update_windows(update_file: str, current_exe: str):
    """Apply update on Windows by creating a batch file to replace and restart."""
    batch_content = f"""
    @echo off
    timeout /t 3 /nobreak >nul
    taskkill /f /im "{os.path.basename(current_exe)}" >nul 2>&1
    move /y "{update_file}" "{current_exe}"
    start "" "{current_exe}"
    del "%~f0"
    """
    batch_path = os.path.join(tempfile.gettempdir(), 'update.bat')
    with open(batch_path, 'w') as batch_file:
        batch_file.write(batch_content)
    
    subprocess.Popen(batch_path, shell=True)
    sys.exit(0)

def _apply_update_unix(update_file: str, current_exe: str):
    """Apply update on Unix-like systems by moving file and exec."""
    shutil.move(update_file, current_exe)
    os.execv(current_exe, sys.argv)
