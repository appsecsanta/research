import io
import os
from urllib.parse import urlparse

from flask import Flask, request, jsonify, send_file
import pdfkit

app = Flask(__name__)

PDFKIT_CONFIG = None
wkhtmltopdf_path = os.environ.get("WKHTMLTOPDF_PATH")
if wkhtmltopdf_path:
    PDFKIT_CONFIG = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)


def is_valid_url(url: str) -> bool:
    try:
        result = urlparse(url)
        return result.scheme in ("http", "https") and bool(result.netloc)
    except Exception:
        return False


@app.route("/api/export/pdf", methods=["POST"])
def export_pdf():
    data = request.get_json(silent=True)
    if not data or "url" not in data:
        return jsonify({"error": "Missing required field 'url' in JSON body"}), 400

    url = data["url"].strip()
    if not is_valid_url(url):
        return jsonify({"error": "Invalid URL. Must start with http:// or https://"}), 400

    options = {
        "page-size": "A4",
        "encoding": "UTF-8",
        "no-stop-slow-scripts": "",
        "enable-javascript": "",
        "javascript-delay": "1000",
        "quiet": "",
    }

    try:
        pdf_bytes = pdfkit.from_url(url, False, options=options, configuration=PDFKIT_CONFIG)
    except OSError as e:
        return jsonify({"error": f"PDF generation failed: {str(e)}"}), 502
    except Exception as e:
        return jsonify({"error": f"Unexpected error during PDF generation: {str(e)}"}), 500

    if not pdf_bytes:
        return jsonify({"error": "PDF generation returned empty content"}), 502

    parsed = urlparse(url)
    filename = parsed.netloc.replace(".", "_") + parsed.path.replace("/", "_")
    if not filename or filename == "_":
        filename = "export"
    filename = filename.strip("_")[:100] + ".pdf"

    buffer = io.BytesIO(pdf_bytes)
    buffer.seek(0)

    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
