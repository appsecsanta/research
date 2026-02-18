from flask import Flask, request, jsonify
import sqlite3

app = Flask(__name__)

# Assume the database and table are already set up.
# Table schema: CREATE TABLE documents (id INTEGER PRIMARY KEY, title TEXT, content TEXT);

@app.route('/api/documents/<int:doc_id>/update', methods=['POST'])
def update_document(doc_id):
    data = request.get_json()
    title = data.get('title')
    content = data.get('content')

    if title is None or content is None:
        return jsonify({'error': 'Missing title or content'}), 400

    try:
        conn = sqlite3.connect('documents.db')
        cursor = conn.cursor()
        cursor.execute('UPDATE documents SET title = ?, content = ? WHERE id = ?', (title, content, doc_id))
        if cursor.rowcount == 0:
            return jsonify({'error': 'Document not found'}), 404
        conn.commit()
    except sqlite3.Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

    return jsonify({'message': 'Document updated successfully'}), 200

if __name__ == '__main__':
    app.run(debug=True)
