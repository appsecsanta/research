# app.py
import logging
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, request

# --- Configuration ---
REQUEST_TIMEOUT_SECONDS = 5
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/91.0.4472.114 Safari/537.36 LinkPreviewBot/1.0"
)

# --- Flask App Initialization ---
app = Flask(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def is_valid_url(url: str) -> bool:
    """Perform a basic validation of the URL structure."""
    if not isinstance(url, str):
        return False
    try:
        result = urlparse(url)
        return all([result.scheme in ["http", "https"], result.netloc])
    except (ValueError, AttributeError):
        return False


def extract_metadata(url: str) -> dict:
    """
    Fetch the content from the URL and extract metadata.

    Args:
        url: The URL to fetch and parse.

    Returns:
        A dictionary containing the title and description.

    Raises:
        requests.exceptions.RequestException: For network-related errors.
        ValueError: If the content is not HTML.
    """
    headers = {"User-Agent": USER_AGENT}
    response = requests.get(
        url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS, allow_redirects=True
    )
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "")
    if "text/html" not in content_type.lower():
        raise ValueError(f"Content-Type is '{content_type}', not text/html")

    soup = BeautifulSoup(response.content, "html.parser")

    title = soup.title.string.strip() if soup.title else None

    description = None
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc and meta_desc.get("content"):
        description = meta_desc["content"].strip()
    else:
        # Fallback to Open Graph description property
        og_desc = soup.find("meta", property="og:description")
        if og_desc and og_desc.get("content"):
            description = og_desc["content"].strip()

    return {"title": title, "description": description}


@app.route("/api/preview", methods=["POST"])
def get_link_preview():
    """
    Accepts a URL in a JSON body, fetches the page,
    and returns its title and meta description.
    """
    if not request.is_json:
        return jsonify({"error": "Request body must be JSON"}), 415

    data = request.get_json()
    url = data.get("url")

    if not is_valid_url(url):
        return jsonify({"error": "A valid 'url' parameter is required"}), 400

    try:
        metadata = extract_metadata(url)
        return jsonify(metadata), 200
    except requests.exceptions.Timeout:
        app.logger.warning(f"Request to {url} timed out.")
        return jsonify({"error": "Request to the URL timed out"}), 408
    except requests.exceptions.RequestException as e:
        app.logger.warning(f"Failed to fetch URL {url}: {e}")
        return jsonify({"error": "Could not fetch content from the URL"}), 422
    except ValueError as e:
        app.logger.warning(f"Content error for URL {url}: {e}")
        return jsonify({"error": str(e)}), 422
    except Exception as e:
        app.logger.error(f"An unexpected error occurred for URL {url}: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred"}), 500


if __name__ == "__main__":
    # For production, use a proper WSGI server like Gunicorn or uWSGI
    # Example: gunicorn --workers 4 --bind 0.0.0.0:5001 app:app
    app.run(host="0.0.0.0", port=5001, debug=False)

# --- requirements.txt ---
# Flask==2.3.3
# requests==2.31.0
# beautifulsoup4==4.12.2
# gunicorn==21.2.0
