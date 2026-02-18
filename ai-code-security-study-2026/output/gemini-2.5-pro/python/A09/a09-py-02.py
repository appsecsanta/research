# middleware.py
import logging
from logging.handlers import RotatingFileHandler
import time
from io import BytesIO
import json
import uuid
from flask import Request

class RequestResponseLoggerMiddleware:
    """
    Flask WSGI middleware to log API requests and their responses.
    """

    def __init__(self, app, log_file='api.log'):
        self.app = app
        self._setup_logger(log_file)

    def _setup_logger(self, log_file: str):
        """Configures the logger for API requests and responses."""
        self.logger = logging.getLogger('api_logger')
        self.logger.setLevel(logging.INFO)
        
        # Use a rotating file handler to prevent log files from growing indefinitely
        handler = RotatingFileHandler(
            log_file, maxBytes=10_000_000, backupCount=5
        )
        
        # The formatter could be customized to include more details
        formatter = logging.Formatter(
            '%(asctime)s - %(message)s'
        )
        handler.setFormatter(formatter)
        
        # Avoid adding handlers multiple times in development environments
        if not self.logger.handlers:
            self.logger.addHandler(handler)

    def __call__(self, environ, start_response):
        """
        The main WSGI interface method. It intercepts the request,
        logs it, passes it to the Flask app, and logs the response.
        """
        request_id = str(uuid.uuid4())
        start_time = time.time()

        # Log the request
        self._log_request(environ, request_id)

        # A wrapper for start_response to capture status and headers
        captured_status = None
        captured_headers = None

        def capture_start_response(status, headers, exc_info=None):
            nonlocal captured_status, captured_headers
            captured_status = status
            captured_headers = headers
            return start_response(status, headers, exc_info)

        # Call the actual application
        response_iterable = self.app(environ, capture_start_response)
        
        # The response body is an iterable. We need to consume it to log it,
        # then recreate it to be returned.
        response_body_parts = []
        try:
            for part in response_iterable:
                response_body_parts.append(part)
        finally:
            if hasattr(response_iterable, 'close'):
                response_iterable.close()

        response_body = b''.join(response_body_parts)
        duration_ms = (time.time() - start_time) * 1000

        # Log the response
        self._log_response(
            request_id,
            captured_status,
            captured_headers,
            response_body,
            duration_ms
        )

        return response_body_parts

    def _log_request(self, environ: dict, request_id: str):
        """Logs the details of an incoming request."""
        request_body = self._read_and_replace_body(environ)
        
        # Use Flask's Request object for easier access to properties
        request = Request(environ)

        log_data = {
            "type": "request",
            "request_id": request_id,
            "method": request.method,
            "url": request.url,
            "headers": dict(request.headers),
            "body": self._format_body(request_body, request.content_type)
        }
        self.logger.info(json.dumps(log_data))

    def _log_response(self, request_id: str, status: str, headers: list, body: bytes, duration_ms: float):
        """Logs the details of an outgoing response."""
        content_type = next((v for k, v in headers if k.lower() == 'content-type'), 'application/octet-stream')
        
        log_data = {
            "type": "response",
            "request_id": request_id,
            "status": status,
            "headers": dict(headers) if headers else {},
            "body": self._format_body(body, content_type),
            "duration_ms": round(duration_ms, 2)
        }
        self.logger.info(json.dumps(log_data))

    def _read_and_replace_body(self, environ: dict) -> bytes:
        """Reads the request body and replaces the input stream."""
        try:
            content_length = int(environ.get('CONTENT_LENGTH', '0'))
        except (ValueError, TypeError):
            content_length = 0

        if content_length > 0:
            body = environ['wsgi.input'].read(content_length)
            environ['wsgi.input'] = BytesIO(body)  # Replace stream for the app
            return body
        return b''

    def _format_body(self, body: bytes, content_type: str):
        """Formats the body for logging, attempting to parse JSON."""
        if not body:
            return None
        
        if 'application/json' in content_type:
            try:
                return json.loads(body.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                # Fallback for malformed JSON or encoding issues
                return f"Could not decode JSON body: {repr(body)}"
        
        # For other content types, return a truncated representation
        if len(body) > 1024: # Limit log size for non-JSON bodies
            return f"<{len(body)} bytes of type {content_type}>"
            
        return repr(body)


# app.py
from flask import Flask, request, jsonify
import os

# --- Flask App Configuration ---
app = Flask(__name__)

# --- API Endpoints for Demonstration ---
@app.route('/api/v1/users', methods=['POST'])
def create_user():
    """Creates a new user."""
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    name = data.get('name')
    email = data.get('email')

    if not name or not email:
        return jsonify({"error": "Missing name or email"}), 400

    # In a real app, you would save the user to a database
    user = {"id": 123, "name": name, "email": email, "status": "created"}
    return jsonify(user), 201

@app.route('/api/v1/status', methods=['GET'])
def get_status():
    """Returns the status of the API."""
    return jsonify({"status": "ok", "version": "1.0.0"})

@app.route('/api/v1/error', methods=['GET'])
def simulate_error():
    """Simulates a server error."""
    return jsonify({"error": "Internal Server Error"}), 500

# --- Middleware Integration ---
# The middleware wraps the Flask application's WSGI interface.
LOG_FILE = os.environ.get("API_LOG_FILE", "api_requests.log")
app.wsgi_app = RequestResponseLoggerMiddleware(app.wsgi_app, log_file=LOG_FILE)

# --- Main Execution ---
if __name__ == '__main__':
    # For production, use a proper WSGI server like Gunicorn or uWSGI.
    # Example: gunicorn --bind 0.0.0.0:5000 app:app
    # The Flask development server is used here for convenience.
    print(f"API logging to: {os.path.abspath(LOG_FILE)}")
    print("Try sending requests:")
    print("curl -X GET http://127.0.0.1:5000/api/v1/status")
    print("curl -X POST -H \"Content-Type: application/json\" -d '{\"name\": \"John Doe\", \"email\": \"john.doe@example.com\"}' http://127.0.0.1:5000/api/v1/users")
    
    app.run(host='0.0.0.0', port=5000)
