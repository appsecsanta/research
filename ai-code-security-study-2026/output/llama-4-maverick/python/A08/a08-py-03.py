import requests
import os
import sys
import zipfile
import shutil
import logging

def get_latest_version(server_url):
    try:
        response = requests.get(f"{server_url}/version")
        response.raise_for_status()
        return response.text.strip()
    except requests.RequestException as e:
        logging.error(f"Failed to retrieve latest version: {e}")
        return None

def download_update(server_url, version):
    try:
        response = requests.get(f"{server_url}/download/{version}")
        response.raise_for_status()
        return response.content
    except requests.RequestException as e:
        logging.error(f"Failed to download update: {e}")
        return None

def apply_update(update_data, current_executable_path):
    try:
        update_zip_path = f"{current_executable_path}.update.zip"
        with open(update_zip_path, "wb") as f:
            f.write(update_data)

        with zipfile.ZipFile(update_zip_path, "r") as zip_ref:
            temp_dir = f"{current_executable_path}.update"
            zip_ref.extractall(temp_dir)

        for filename in os.listdir(temp_dir):
            if filename.endswith(".exe"):
                new_executable_path = os.path.join(temp_dir, filename)
                shutil.move(new_executable_path, current_executable_path)

        shutil.rmtree(temp_dir)
        os.remove(update_zip_path)
    except Exception as e:
        logging.error(f"Failed to apply update: {e}")

def auto_update(server_url, current_version, current_executable_path):
    latest_version = get_latest_version(server_url)
    if latest_version is None or latest_version == current_version:
        return

    update_data = download_update(server_url, latest_version)
    if update_data is None:
        return

    apply_update(update_data, current_executable_path)

    # Restart the application
    os.execl(current_executable_path, *sys.argv)

if __name__ == "__main__":
    server_url = "https://example.com/updates"
    current_version = "1.0.0"
    current_executable_path = sys.executable
    auto_update(server_url, current_version, current_executable_path)
