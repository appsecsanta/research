import logging
import traceback
from functools import wraps
from logging.handlers import RotatingFileHandler

from flask import Flask, jsonify, request

# --- Constants ---
LOG_FILE = "error.log"
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
LOG_BACKUP_COUNT = 5
MAX_BODY_LOG_SIZE = 4096  # Log up to 4KB of the request body


def setup_error_logging(app_name: str) -> logging.Logger:
    """
    Configures a rotating file logger for application errors.

    Args:
        app_name: The name of the application, used for the logger name.

    Returns:
        A configured logger instance.
    """
    logger = logging.getLogger(app_name)
    logger.setLevel(logging.ERROR)

    # Prevent log messages from propagating to the root logger
    logger.propagate = False

    # Create a rotating file handler
    handler = RotatingFileHandler(
        LOG_FILE, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT
    )

    # Create a formatter and set it for the handler
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)

    # Add the handler to the logger if it doesn't have one already
    if not logger.handlers:
        logger.addHandler(handler)

    return logger


def log_endpoint_errors(logger: logging.Logger):
    """
    A decorator factory that creates a decorator to log exceptions from Flask endpoints.

    Args:
        logger: The logger instance to use for logging errors.

    Returns:
        A decorator function.
    """

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except Exception as e:
                # Safely get request body, truncating if it's too large
                try:
                    body = request.get_data(as_text=True)
                    if len(body) > MAX_BODY_LOG_SIZE:
                        body = body[:MAX_BODY_LOG_SIZE] + "... (truncated)"
                except Exception:
                    body = "Could not read request body."

                # Construct detailed log message
                log_message = (
                    f"Unhandled exception on endpoint: {request.path}\n"
                    f"Method: {request.method}\n"
                    f"Client IP: {request.remote_addr}\n"
                    f"User Agent: {request.user_agent}\n"
                    f"Headers: {dict(request.headers)}\n"
                    f"Body: {body}\n"
                    f"Exception Type: {type(e).__name__}\n"
                    f"Exception Message: {e}\n"
                    f"Traceback:\n{traceback.format_exc()}"
                )

                logger.error(log_message)

                # Return a generic error response to the client
                error_response = {
                    "error": "Internal Server Error",
                    "message": "An unexpected error occurred. Please try again later.",
                }
                return jsonify(error_response), 500

        return wrapper

    return decorator


# --- Flask Application Setup ---

app = Flask(__name__)

# Initialize the error logger
error_logger = setup_error_logging("MyFlaskAppErrors")

# Create the decorator instance
log_errors = log_endpoint_errors(error_logger)


# --- Example Endpoints ---


@app.route("/success")
@log_errors
def success_endpoint():
    """An endpoint that always succeeds."""
    return jsonify({"status": "success", "data": "This endpoint works!"}), 200


@app.route("/divide_by_zero")
@log_errors
def error_endpoint():
    """An endpoint that will raise a ZeroDivisionError."""
    result = 1 / 0
    return jsonify({"result": result})  # This line will not be reached


@app.route("/value_error", methods=["POST"])
@log_errors
def value_error_endpoint():
    """An endpoint that will raise a ValueError if 'number' is not an int."""
    data = request.get_json()
    if not data or "number" not in data:
        return jsonify({"error": "Missing 'number' in request body"}), 400

    # This will raise a ValueError if 'number' is not a valid integer string
    number = int(data["number"])
    return jsonify({"status": "success", "number_squared": number**2})


if __name__ == "__main__":
    # Run the app with debug=False to ensure the decorator handles exceptions
    # In a real production environment, you would use a WSGI server like Gunicorn or uWSGI
    print("Flask app running. Try accessing:")
    print(" - http://127.0.0.1:5000/success (should work)")
    print(" - http://127.0.0.1:5000/divide_by_zero (should fail and log)")
    print(
        " - curl -X POST -H \"Content-Type: application/json\" "
        "-d '{\"number\": \"abc\"}' http://127.0.0.1:5000/value_error (should fail and log)"
    )
    print(f"Errors will be logged to '{LOG_FILE}' in the current directory.")
    app.run(host="0.0.0.0", port=5000, debug=False)
