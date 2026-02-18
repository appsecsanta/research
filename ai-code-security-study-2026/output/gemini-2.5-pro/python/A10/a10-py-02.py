# app.py
import logging
import sqlite3
import threading
from urllib.parse import urlparse

import requests
from flask import Flask, g, jsonify, request

# --- Constants ---
DATABASE_FILE = "webhooks.db"
WEBHOOK_TIMEOUT_SECONDS = 10

# --- Application Setup ---
app = Flask(__name__)
app.config["JSONIFY_PRETTYPRINT_REGULAR"] = True

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


# --- Database Management ---
def get_db():
    """Get a database connection from the Flask g object or create a new one."""
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE_FILE)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception):
    """Close the database connection at the end of the request."""
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def init_db():
    """Initialize the database with the required schema."""
    with app.app_context():
        db = get_db()
        with app.open_resource("schema.sql", mode="r") as f:
            db.cursor().executescript(f.read())
        db.commit()
    logging.info("Database initialized.")


# --- Webhook Logic ---
def is_valid_url(url: str) -> bool:
    """Perform a basic validation of the URL format."""
    if not isinstance(url, str):
        return False
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc]) and result.scheme in ["http", "httpss"]
    except (ValueError, AttributeError):
        return False


def send_webhook_request(url: str, data: dict):
    """
    Send a POST request to a single webhook URL in a separate thread.
    Handles request exceptions and logs the outcome.
    """
    try:
        response = requests.post(
            url,
            json=data,
            timeout=WEBHOOK_TIMEOUT_SECONDS,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        logging.info(
            f"Successfully sent webhook to {url}. Status: {response.status_code}"
        )
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to send webhook to {url}: {e}")


def trigger_webhooks(event_type: str, payload: dict):
    """
    Fetch all registered webhook URLs and dispatch an event to each of them
    concurrently.
    """
    # This function opens its own database connection because it might be
    # called from a background task outside of a request context.
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT url FROM webhooks")
        rows = cursor.fetchall()
    finally:
        if conn:
            conn.close()

    if not rows:
        logging.info("No webhooks registered. Skipping trigger.")
        return

    event_data = {"event_type": event_type, "payload": payload}

    for row in rows:
        url = row["url"]
        thread = threading.Thread(target=send_webhook_request, args=(url, event_data))
        thread.start()


# --- API Endpoints ---
@app.route("/api/webhooks/register", methods=["POST"])
def register_webhook():
    """
    Register a new webhook URL.
    Expects a JSON payload with a 'url' key.
    """
    data = request.get_json()
    if not data or "url" not in data:
        return jsonify({"error": "Missing 'url' in request body"}), 400

    url = data["url"]
    if not is_valid_url(url):
        return jsonify({"error": "Invalid URL format"}), 400

    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("INSERT INTO webhooks (url) VALUES (?)", (url,))
        db.commit()
        webhook_id = cursor.lastrowid
        logging.info(f"Registered new webhook: {url} (ID: {webhook_id})")
        return (
            jsonify({"message": "Webhook registered successfully", "id": webhook_id}),
            201,
        )
    except sqlite3.IntegrityError:
        return jsonify({"error": "Webhook URL already registered"}), 409
    except Exception as e:
        logging.error(f"Database error on webhook registration: {e}")
        return jsonify({"error": "An internal server error occurred"}), 500


# --- Example Event Trigger Endpoint ---
@app.route("/api/events/create_order", methods=["POST"])
def create_order_event():
    """
    An example endpoint that simulates an 'order.created' event and triggers
    all registered webhooks.
    """
    order_data = request.get_json()
    if not order_data or "order_id" not in order_data or "amount" not in order_data:
        return jsonify({"error": "Missing 'order_id' or 'amount'"}), 400

    logging.info(
        f"Simulating 'order.created' event for order: {order_data.get('order_id')}"
    )

    # In a real application, you would first save the order to your database.
    # Then, trigger the webhooks.
    trigger_webhooks(event_type="order.created", payload=order_data)

    return jsonify({"message": "Order created event triggered successfully"}), 200


if __name__ == "__main__":
    # Create schema.sql file if it doesn't exist
    with open("schema.sql", "w") as f:
        f.write(
            """
        CREATE TABLE IF NOT EXISTS webhooks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        )
    init_db()
    app.run(host="0.0.0.0", port=5001)
