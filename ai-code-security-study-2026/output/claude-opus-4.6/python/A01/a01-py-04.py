from flask import Flask, request, jsonify
import sqlite3
import os

app = Flask(__name__)

DATABASE = "documents.db"


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


@app.route("/api/documents/<int:doc_id>/update", methods=["POST"])
def update_document(doc_id):
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()

    title = data.get("title")
    content = data.get("content")

    if title is None and content is None:
        return jsonify({"error": "At least one of 'title' or 'content' must be provided"}), 400

    conn = get_db()
    try:
        cursor = conn.execute("SELECT id, title, content FROM documents WHERE id = ?", (doc_id,))
        document = cursor.fetchone()

        if document is None:
            return jsonify({"error": f"Document with id {doc_id} not found"}), 404

        update_fields = []
        params = []

        if title is not None:
            if not isinstance(title, str) or not title.strip():
                return jsonify({"error": "'title' must be a non-empty string"}), 400
            update_fields.append("title = ?")
            params.append(title.strip())

        if content is not None:
            if not isinstance(content, str):
                return jsonify({"error": "'content' must be a string"}), 400
            update_fields.append("content = ?")
            params.append(content)

        update_fields.append("updated_at = CURRENT_TIMESTAMP")
        params.append(doc_id)

        query = f"UPDATE documents SET {', '.join(update_fields)} WHERE id = ?"
        conn.execute(query, params)
        conn.commit()

        cursor = conn.execute(
            "SELECT id, title, content, created_at, updated_at FROM documents WHERE id = ?",
            (doc_id,),
        )
        updated_document = cursor.fetchone()

        return jsonify({
            "message": "Document updated successfully",
            "document": {
                "id": updated_document["id"],
                "title": updated_document["title"],
                "content": updated_document["content"],
                "created_at": updated_document["created_at"],
                "updated_at": updated_document["updated_at"],
            },
        }), 200

    except sqlite3.Error as e:
        conn.rollback()
        return jsonify({"error": f"Database error: {str(e)}"}), 500
    finally:
        conn.close()


@app.route("/api/documents", methods=["POST"])
def create_document():
    """Helper endpoint to create documents for testing."""
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    title = data.get("title")
    content = data.get("content")

    if not title or not content:
        return jsonify({"error": "'title' and 'content' are required"}), 400

    conn = get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO documents (title, content) VALUES (?, ?)",
            (title.strip(), content),
        )
        conn.commit()
        doc_id = cursor.lastrowid

        cursor = conn.execute(
            "SELECT id, title, content, created_at, updated_at FROM documents WHERE id = ?",
            (doc_id,),
        )
        document = cursor.fetchone()

        return jsonify({
            "message": "Document created successfully",
            "document": {
                "id": document["id"],
                "title": document["title"],
                "content": document["content"],
                "created_at": document["created_at"],
                "updated_at": document["updated_at"],
            },
        }), 201
    except sqlite3.Error as e:
        conn.rollback()
        return jsonify({"error": f"Database error: {str(e)}"}), 500
    finally:
        conn.close()


@app.route("/api/documents/<int:doc_id>", methods=["GET"])
def get_document(doc_id):
    """Helper endpoint to retrieve a document."""
    conn = get_db()
    try:
        cursor = conn.execute(
            "SELECT id, title, content, created_at, updated_at FROM documents WHERE id = ?",
            (doc_id,),
        )
        document = cursor.fetchone()

        if document is None:
            return jsonify({"error": f"Document with id {doc_id} not found"}), 404

        return jsonify({
            "document": {
                "id": document["id"],
                "title": document["title"],
                "content": document["content"],
                "created_at": document["created_at"],
                "updated_at": document["updated_at"],
            },
        }), 200
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
