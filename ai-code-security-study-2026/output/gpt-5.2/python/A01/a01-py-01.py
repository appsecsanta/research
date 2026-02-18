import os
import sqlite3
from typing import Optional

from flask import Flask, g, jsonify


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["DATABASE_PATH"] = os.environ.get("DATABASE_PATH", "app.db")

    def get_db() -> sqlite3.Connection:
        db: Optional[sqlite3.Connection] = getattr(g, "_db", None)
        if db is None:
            db = sqlite3.connect(app.config["DATABASE_PATH"])
            db.row_factory = sqlite3.Row
            g._db = db
        return db

    @app.teardown_appcontext
    def close_db(_exc: Optional[BaseException]) -> None:
        db: Optional[sqlite3.Connection] = getattr(g, "_db", None)
        if db is not None:
            db.close()

    @app.get("/api/users/<int:user_id>/profile")
    def get_user_profile(user_id: int):
        if user_id <= 0:
            return jsonify({"error": "Invalid user_id"}), 400

        db = get_db()
        row = db.execute(
            """
            SELECT id, email, phone_number, address
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()

        if row is None:
            return jsonify({"error": "User not found"}), 404

        return jsonify(
            {
                "user_id": row["id"],
                "email": row["email"],
                "phone_number": row["phone_number"],
                "address": row["address"],
            }
        ), 200

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
