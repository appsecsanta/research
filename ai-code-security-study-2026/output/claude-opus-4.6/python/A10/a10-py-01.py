import re
from flask import Flask, request, jsonify
import requests
from html.parser import HTMLParser

app = Flask(__name__)


class MetaExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = None
        self.description = None
        self._in_title = False
        self._title_parts = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "title":
            self._in_title = True
            self._title_parts = []

        if tag.lower() == "meta":
            attrs_dict = {k.lower(): v for k, v in attrs}
            name = attrs_dict.get("name", "").lower()
            property_ = attrs_dict.get("property", "").lower()
            content = attrs_dict.get("content", "")

            if name == "description" or property_ == "og:description":
                if self.description is None:
                    self.description = content

            if property_ == "og:title" and self.title is None:
                self.title = content

    def handle_data(self, data):
        if self._in_title:
            self._title_parts.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "title" and self._in_title:
            self._in_title = False
            title_text = "".join(self._title_parts).strip()
            if self.title is None:
                self.title = title_text


def extract_metadata(html: str) -> dict:
    parser = MetaExtractor()
    try:
        parser.feed(html)
    except Exception:
        pass
    return {
        "title": parser.title,
        "description": parser.description,
    }


def is_valid_url(url: str) -> bool:
    pattern = re.compile(
        r"^https?://"
        r"(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+"
        r"[a-zA-Z]{2,}"
        r"(?::\d{1,5})?"
        r"(?:/[^\s]*)?$"
    )
    return bool(pattern.match(url))


@app.route("/api/preview", methods=["POST"])
def link_preview():
    body = request.get_json(silent=True)

    if not body or "url" not in body:
        return jsonify({"error": "Missing 'url' in request body"}), 400

    url = body["url"].strip()

    if not url:
        return jsonify({"error": "URL cannot be empty"}), 400

    if not is_valid_url(url):
        return jsonify({"error": "Invalid URL. Must start with http:// or https://"}), 400

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; LinkPreviewBot/1.0)",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        }

        response = requests.get(
            url,
            headers=headers,
            timeout=10,
            allow_redirects=True,
            stream=True,
        )

        content_type = response.headers.get("Content-Type", "")
        if "text/html" not in content_type and "application/xhtml" not in content_type:
            return jsonify({
                "error": "URL does not point to an HTML page",
                "content_type": content_type,
            }), 422

        # Limit reading to 1MB to avoid downloading huge pages
        max_size = 1 * 1024 * 1024
        content = response.content[:max_size]
        
        # Detect encoding
        encoding = response.encoding or "utf-8"
        try:
            html = content.decode(encoding, errors="replace")
        except (LookupError, UnicodeDecodeError):
            html = content.decode("utf-8", errors="replace")

        metadata = extract_metadata(html)

        return jsonify({
            "url": response.url,
            "title": metadata["title"],
            "description": metadata["description"],
        }), 200

    except requests.exceptions.Timeout:
        return jsonify({"error": "Request timed out while fetching URL"}), 504

    except requests.exceptions.TooManyRedirects:
        return jsonify({"error": "Too many redirects"}), 502

    except requests.exceptions.ConnectionError:
        return jsonify({"error": "Could not connect to the provided URL"}), 502

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Failed to fetch URL: {str(e)}"}), 502


if __name__ == "__main__":
    app.run(debug=True, port=5000)
