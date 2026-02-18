import os
import sqlite3
import uuid
from datetime import datetime

import click
from flask import (
    Flask,
    g,
    jsonify,
    request,
    send_from_directory,
    url_for,
)
from werkzeug.utils import secure_filename

# --- Configuration ---
DATABASE = "file_metadata.db"
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"txt", "pdf", "png", "jpg", "jpeg", "gif"}

# --- Flask App Initialization ---
app = Flask(__name__)
app.config["DATABASE"] = DATABASE
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB upload limit


# --- Database Management ---
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(
            app.config["DATABASE"], detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(app.config["DATABASE"])
    schema = """
    DROP TABLE IF EXISTS files;
    CREATE TABLE files (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      original_filename TEXT NOT NULL,
      saved_filename TEXT NOT NULL UNIQUE,
      upload_date TIMESTAMP NOT NULL,
      uploader TEXT NOT NULL
    );
    """
    db.cursor().executescript(schema)
    db.commit()
    db.close()


@app.cli.command("init-db")
def init_db_command():
    """Clear existing data and create new tables."""
    init_db()
    click.echo("Initialized the database.")


# --- Helper Functions ---
def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# --- Application Setup ---
@app.before_request
def ensure_upload_folder_exists():
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


# --- API Endpoints ---
@app.route("/api/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file part in the request"}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"error": "No file selected for uploading"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "File type not allowed"}), 400

    try:
        original_filename = secure_filename(file.filename)
        file_extension = original_filename.rsplit(".", 1)[1].lower()
        saved_filename = f"{uuid.uuid4().hex}.{file_extension}"
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], saved_filename)

        file.save(filepath)

        uploader = request.headers.get("X-Uploader-ID", "anonymous")
        upload_date = datetime.utcnow()

        db = get_db()
        db.execute(
            "INSERT INTO files (original_filename, saved_filename, upload_date, uploader) VALUES (?, ?, ?, ?)",
            (original_filename, saved_filename, upload_date, uploader),
        )
        db.commit()

        file_url = url_for("get_uploaded_file", filename=saved_filename, _external=True)

        return (
            jsonify({"message": "File uploaded successfully", "file_url": file_url}),
            201,
        )

    except Exception as e:
        app.logger.error(f"File upload failed: {e}")
        return jsonify({"error": "An internal error occurred during file upload"}), 500


@app.route("/uploads/<path:filename>", methods=["GET"])
def get_uploaded_file(filename: str):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


if __name__ == "__main__":
    app.run(debug=True)
