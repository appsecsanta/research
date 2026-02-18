import os
from typing import Any, Dict, Tuple

from flask import Flask, Response, jsonify
from werkzeug.exceptions import HTTPException, InternalServerError, NotFound

# --- Type Definitions ---
ErrorResponsePayload = Dict[str, Dict[str, Any]]
ErrorResponse = Tuple[Response, int]


# --- Flask App Initialization ---
app = Flask(__name__)
# In a real app, this would be configured through environment variables
app.config["DEBUG"] = os.environ.get("FLASK_DEBUG", "False").lower() == "true"


# --- Error Handlers ---

@app.errorhandler(NotFound)
def handle_not_found(error: NotFound) -> ErrorResponse:
    """Handler for 404 Not Found errors."""
    payload: ErrorResponsePayload = {
        "error": {
            "code": error.code,
            "name": error.name,
            "description": error.description,
        }
    }
    return jsonify(payload), error.code or 404


@app.errorhandler(InternalServerError)
def handle_internal_server_error(error: InternalServerError) -> ErrorResponse:
    """Handler for 500 Internal Server Error."""
    # In a production environment, you should not expose the original description
    # to the client for security reasons.
    description = "An internal server error occurred."
    if app.config["DEBUG"]:
        description = error.description or description

    payload: ErrorResponsePayload = {
        "error": {
            "code": error.code,
            "name": error.name,
            "description": description,
        }
    }
    return jsonify(payload), error.code or 500


@app.errorhandler(Exception)
def handle_generic_exception(error: Exception) -> ErrorResponse:
    """
    Generic error handler for all other exceptions.
    Catches werkzeug.exceptions.HTTPException and any other Python exception.
    """
    if isinstance(error, HTTPException):
        # Handle HTTP errors (e.g., 405 Method Not Allowed)
        payload: ErrorResponsePayload = {
            "error": {
                "code": error.code,
                "name": error.name,
                "description": error.description,
            }
        }
        status_code = error.code or 500
        return jsonify(payload), status_code
    else:
        # Handle non-HTTP, unexpected errors
        # In a production app, you should log this error.
        # e.g., app.logger.exception("An unhandled exception occurred: %s", error)
        payload: ErrorResponsePayload = {
            "error": {
                "code": 500,
                "name": "Internal Server Error",
                "description": "An unexpected error occurred on the server.",
            }
        }
        return jsonify(payload), 500


# --- Example Routes to Demonstrate Error Handling ---

@app.route("/")
def index() -> Response:
    """A successful endpoint that returns a welcome message."""
    return jsonify({"status": "ok", "message": "Welcome to the API!"})


@app.route("/error/internal")
def trigger_internal_error() -> None:
    """An endpoint that deliberately raises a non-HTTP exception."""
    # This will be caught by the generic exception handler and return a 500 error.
    raise ValueError("This is a deliberate application error.")


# Accessing a non-existent route like `/notfound` will trigger the 404 handler.
# Flask handles this automatically.


if __name__ == "__main__":
    # For production, use a proper WSGI server like Gunicorn or uWSGI.
    # The debug flag should be set to False in a production environment.
    app.run(host="0.0.0.0", port=5001)
