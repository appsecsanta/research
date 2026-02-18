import functools
import logging
import traceback
import uuid
from datetime import datetime, timezone
from flask import Flask, request, jsonify

# Configure file logger
logger = logging.getLogger("flask_error_logger")
logger.setLevel(logging.ERROR)

file_handler = logging.FileHandler("flask_errors.log")
file_handler.setLevel(logging.ERROR)

formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)


def log_errors(f):
    """
    Decorator that wraps Flask endpoint functions to catch exceptions,
    log full error details to a file, and return a structured error
    response to the client.
    """

    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as exc:
            error_id = str(uuid.uuid4())
            timestamp = datetime.now(timezone.utc).isoformat()

            # Gather request context
            request_context = {
                "error_id": error_id,
                "timestamp": timestamp,
                "endpoint": request.endpoint,
                "method": request.method,
                "url": request.url,
                "path": request.path,
                "query_string": request.query_string.decode("utf-8", errors="replace"),
                "remote_addr": request.remote_addr,
                "user_agent": str(request.user_agent),
                "headers": {
                    k: v
                    for k, v in request.headers
                    if k.lower() not in ("authorization", "cookie", "x-api-key")
                },
                "referrer": request.referrer,
                "content_type": request.content_type,
            }

            # Safely capture request body
            try:
                if request.is_json:
                    request_context["body"] = request.get_json(silent=True)
                elif request.form:
                    request_context["body"] = dict(request.form)
                else:
                    body_bytes = request.get_data(as_text=True)
                    request_context["body"] = (
                        body_bytes[:2000] if body_bytes else None
                    )
            except Exception:
                request_context["body"] = "<unable to read body>"

            # Capture view function args/kwargs
            request_context["view_args"] = request.view_args
            request_context["function_name"] = f.__qualname__
            request_context["function_module"] = f.__module__

            # Full traceback
            tb = traceback.format_exc()

            log_message = (
                f"\n{'=' * 80}\n"
                f"ERROR ID: {error_id}\n"
                f"TIMESTAMP: {timestamp}\n"
                f"FUNCTION: {f.__module__}.{f.__qualname__}\n"
                f"EXCEPTION TYPE: {type(exc).__name__}\n"
                f"EXCEPTION MESSAGE: {exc}\n"
                f"METHOD: {request_context['method']}\n"
                f"URL: {request_context['url']}\n"
                f"REMOTE ADDR: {request_context['remote_addr']}\n"
                f"USER AGENT: {request_context['user_agent']}\n"
                f"CONTENT TYPE: {request_context['content_type']}\n"
                f"QUERY STRING: {request_context['query_string']}\n"
                f"VIEW ARGS: {request_context['view_args']}\n"
                f"HEADERS: {request_context['headers']}\n"
                f"BODY: {request_context.get('body')}\n"
                f"TRACEBACK:\n{tb}\n"
                f"{'=' * 80}"
            )

            logger.error(log_message)

            # Determine appropriate status code
            status_code = getattr(exc, "code", 500)
            if not isinstance(status_code, int) or status_code < 400 or status_code > 599:
                status_code = 500

            response = {
                "error": {
                    "error_id": error_id,
                    "message": "An internal server error occurred."
                    if status_code == 500
                    else str(exc),
                    "status": status_code,
                    "timestamp": timestamp,
                }
            }

            return jsonify(response), status_code

    return decorated_function


# --- Demo application ---

app = Flask(__name__)


@app.route("/")
@log_errors
def index():
    return jsonify({"message": "Hello, World!"})


@app.route("/users/<int:user_id>")
@log_errors
def get_user(user_id):
    # Simulate a database lookup that fails
    users = {1: "Alice", 2: "Bob"}
    name = users[user_id]  # KeyError if user_id not in dict
    return jsonify({"user_id": user_id, "name": name})


@app.route("/divide")
@log_errors
def divide():
    a = int(request.args.get("a", 10))
    b = int(request.args.get("b", 0))
    result = a / b  # ZeroDivisionError when b=0
    return jsonify({"result": result})


@app.route("/data", methods=["POST"])
@log_errors
def process_data():
    data = request.get_json(force=True)
    # Simulate processing that raises an unexpected error
    value = data["required_key"]  # KeyError if missing
    return jsonify({"processed": value.upper()})


if __name__ == "__main__":
    app.run(debug=False, port=5000)
