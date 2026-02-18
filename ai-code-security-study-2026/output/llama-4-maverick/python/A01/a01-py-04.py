from flask import Flask, request, jsonify
import sqlite3
import json

app = Flask(__name__)

# Database connection settings
DATABASE_NAME = 'documents.db'

# Create a connection to the SQLite database
def get_db_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/api/documents/<int:doc_id>/update', methods=['POST'])
def update_document(doc_id):
    data = request.get_json()
    if not data or 'title' not in data or 'content' not in data:
        return jsonify({'error': 'Missing required fields'}), 400
    
    conn = get_db_connection()
    try:
        conn.execute('UPDATE documents SET title = ?, content = ? WHERE id = ?', 
                     (data['title'], data['content'], doc_id))
        if conn.total_changes == 0:
            return jsonify({'error': 'Document not found'}), 404
        conn.commit()
    except sqlite3.Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()
    
    return jsonify({'message': 'Document updated successfully'}), 200

if __name__ == '__main__':
    app.run(debug=True)
