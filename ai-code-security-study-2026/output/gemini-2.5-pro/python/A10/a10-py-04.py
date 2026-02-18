# main.py
import logging
from io import BytesIO

from flask import Flask, jsonify, request, send_file
from validators import url as validate_url
from weasyprint import HTML
from weasyprint.urls import URLFetchingError

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

app = Flask(__name__)


@app.route("/api/export/pdf", methods=["POST"])
def export_to_pdf():
    """
    Accepts a URL in a JSON payload and returns a PDF version of the webpage.
    ---
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            url:
              type: string
              description: The URL of the webpage to convert to PDF.
              example: "https://www.google.com"
          required:
            - url
    responses:
      200:
        description: A PDF file generated from the URL.
        content:
          application/pdf:
            schema:
              type: string
              format: binary
      400:
        description: Bad request due to invalid JSON, missing URL, or invalid URL.
      500:
        description: Internal server error during PDF generation.
    """
    if not request.is_json:
        return jsonify({"error": "Request body must be JSON"}), 400

    data = request.get_json()
    url = data.get("url")

    if not url:
        return jsonify({"error": "Missing 'url' field in request body"}), 400

    if not validate_url(url):
        return jsonify({"error": f"Invalid URL provided: {url}"}), 400

    try:
        logging.info(f"Generating PDF for URL: {url}")
        pdf_bytes = HTML(url=url).write_pdf()
        pdf_buffer = BytesIO(pdf_bytes)
        pdf_buffer.seek(0)

        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name="export.pdf",
            mimetype="application/pdf",
        )

    except URLFetchingError as e:
        logging.error(f"Failed to fetch URL '{url}': {e}")
        return (
            jsonify({"error": f"Could not fetch content from the provided URL: {e}"}),
            400,
        )
    except Exception as e:
        logging.error(f"An unexpected error occurred while generating PDF for '{url}': {e}")
        return jsonify({"error": "An internal error occurred during PDF generation"}), 500


@app.route("/")
def health_check():
    """A simple health check endpoint."""
    return "PDF Export Service is running."


if __name__ == "__main__":
    # For development only. In production, use a WSGI server like Gunicorn.
    # Example: gunicorn --bind 0.0.0.0:8000 main:app
    app.run(host="0.0.0.0", port=5001, debug=True)
