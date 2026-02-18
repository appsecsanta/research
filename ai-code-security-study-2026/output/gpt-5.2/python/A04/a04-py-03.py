import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from flask import Flask, g, jsonify, request, send_from_directory, url_for
from werkzeug.utils import secure_filename


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_UPLOADS_DIR = BASE_DIR / "uploads"
DEFAULT_DB_PATH = BASE_DIR / "app.db"


def create_app() -> Flask:
    app = Flask(__name__)

    app.config.from_mapping(
        UPLOADS_DIR=str(DEFAULT_UPLOADS_DIR),
        DATABASE=str(DEFAULT_DB_PATH),
        MAX_CONTENT_LENGTH=100 * 1024 * 1024,  # 100MB
    )

    Path(app.config["UPLOADS_DIR"]).mkdir(parents=True, exist_ok=True)

    def get_db() -> sqlite3.Connection:
        if "db" not in g:
            conn = sqlite3.connect(app.config["DATABASE"], detect_types=sqlite3.PARSE_DECLTYPES)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            g.db = conn
        return g.db

    def init_db() -> None:
        db = get_db()
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS uploads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stored_filename TEXT NOT NULL UNIQUE,
                original_filename TEXT NOT NULL,
                uploader TEXT NOT NULL,
                upload_date TEXT NOT NULL
            );
            """
        )
        db.commit()

    @app.before_request
    def _ensure_db_initialized():
        init_db()

    @app.teardown_appcontext
    def close_db(_exc):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    @app.get("/uploads/<path:filename>")
    def uploaded_file(filename: str):
        return send_from_directory(app.config["UPLOADS_DIR"], filename, as_attachment=False)

    @app.post("/api/upload")
    def upload():
        if "file" not in request.files:
            return jsonify({"error": "Missing file field 'file'"}), 400

        file = request.files["file"]
        if not file or file.filename is None or file.filename.strip() == "":
            return jsonify({"error": "No file selected"}), 400

        uploader = (request.form.get("uploader") or "").strip()
        if not uploader:
            return jsonify({"error": "Missing form field 'uploader'"}), 400

        original_filename = secure_filename(file.filename)
        if not original_filename:
            return jsonify({"error": "Invalid filename"}), 400

        ext = Path(original_filename).suffix
        stored_filename = f"{uuid4().hex}{ext}"
        upload_path = Path(app.config["UPLOADS_DIR"]) / stored_filename

        file.save(str(upload_path))

        upload_date = datetime.now(timezone.utc).isoformat()

        db = get_db()
        db.execute(
            """
            INSERT INTO uploads (stored_filename, original_filename, uploader, upload_date)
            VALUES (?, ?, ?, ?)
            """,
            (stored_filename, original_filename, uploader, upload_date),
        )
        db.commit()

        file_url = url_for("uploaded_file", filename=stored_filename, _external=True)
        return jsonify({"url": file_url}), 201

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
