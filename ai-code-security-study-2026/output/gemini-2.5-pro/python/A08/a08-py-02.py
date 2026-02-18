# app.py
import base64
import binascii
import logging
import pickle
import sqlite3
from typing import Any, List

import click
from flask import Flask, Response, g, jsonify, request

# --- Configuration ---
DATABASE = "data.db"
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

# --- Flask Application Setup ---
app = Flask(__name__)
app.config["DATABASE"] = DATABASE


# --- Database Management ---
def get_db() -> sqlite3.Connection:
    """
    Connect to the application's configured database. The connection
    is unique for each request and will be reused if this is called
    again.
    """
    if "db" not in g:
        try:
            g.db = sqlite3.connect(
                app.config["DATABASE"], detect_types=sqlite3.PARSE_DECLTYPES
            )
            g.db.row_factory = sqlite3.Row
            logger.info("Database connection established.")
        except sqlite3.Error as e:
            logger.error(f"Database connection failed: {e}")
            raise
    return g.db


@app.teardown_appcontext
def close_db(e: Exception = None) -> None:
    """
    If a connection was created, close it at the end of the request.
    """
    db = g.pop("db", None)
    if db is not None:
        db.close()
        logger.info("Database connection closed.")


def init_db() -> None:
    """
    Initialize the database schema by executing the schema.sql file.
    """
    try:
        db = get_db()
        with app.open_resource("schema.sql") as f:
            db.executescript(f.read().decode("utf8"))
        logger.info("Database initialized.")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


@app.cli.command("init-db")
def init_db_command() -> None:
    """Clear the existing data and create new tables."""
    init_db()
    click.echo("Initialized the database.")


# --- API Endpoint ---
@app.route("/api/import", methods=["POST"])
def import_data() -> Response:
    """
    Accepts a base64-encoded, pickled list of objects, deserializes them,
    and stores them in the database.
    """
    if not request.data:
        logger.warning("Received empty request body.")
        return jsonify({"error": "Request body cannot be empty."}), 400

    # 1. Decode Base64
    try:
        serialized_data = base64.b64decode(request.data, validate=True)
    except binascii.Error as e:
        logger.error(f"Base64 decoding failed: {e}")
        return jsonify({"error": "Invalid base64-encoded payload."}), 400

    # 2. Deserialize Pickle
    # WARNING: Unpickling data from untrusted sources is a security risk.
    # This implementation assumes the client is trusted. In a real-world
    # scenario, a safer serialization format like JSON or Protobuf is recommended.
    try:
        objects = pickle.loads(serialized_data)
    except (pickle.UnpicklingError, TypeError, ValueError) as e:
        logger.error(f"Deserialization failed: {e}")
        return jsonify({"error": "Failed to deserialize payload."}), 400

    if not isinstance(objects, list):
        logger.warning("Payload did not deserialize to a list.")
        return jsonify({"error": "Payload must be a list of objects."}), 400

    # 3. Store in Database
    imported_count = 0
    db = get_db()
    cursor = db.cursor()

    try:
        for obj in objects:
            # Basic validation for object structure
            if not hasattr(obj, "name") or not hasattr(obj, "price"):
                logger.warning(f"Skipping invalid object: {obj}")
                continue

            cursor.execute(
                "INSERT INTO products (name, price) VALUES (?, ?)",
                (obj.name, obj.price),
            )
            imported_count += 1
        db.commit()
        logger.info(f"Successfully imported {imported_count} records.")
    except sqlite3.Error as e:
        db.rollback()
        logger.error(f"Database transaction failed: {e}")
        return (
            jsonify({"error": "An internal database error occurred."}),
            500,
        )
    except Exception as e:
        db.rollback()
        logger.error(f"An unexpected error occurred during import: {e}")
        return (
            jsonify({"error": "An unexpected internal error occurred."}),
            500,
        )

    return (
        jsonify(
            {
                "status": "success",
                "imported_count": imported_count,
                "total_objects_received": len(objects),
            }
        ),
        201,
    )


if __name__ == "__main__":
    # For production, use a proper WSGI server like Gunicorn or uWSGI
    # Example: gunicorn --bind 0.0.0.0:8000 app:app
    app.run(host="0.0.0.0", port=5000, debug=True)
