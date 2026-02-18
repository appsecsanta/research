from flask import Flask, request, jsonify
import sqlite3

app = Flask(__name__)

@app.route('/api/documents/<int:doc_id>/update', methods=['POST'])
def update_document(doc_id):
    data = request.get_json()
    title = data.get('title')
    content = data.get('content')

    if not title or not content:
        return jsonify({'error': 'Title and content are required'}), 400

    try:
        conn = sqlite3.connect('documents.db')
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE documents
            SET title = ?, content = ?
            WHERE id = ?
        ''', (title, content, doc_id))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Document updated successfully'}), 200
    except sqlite3.Error as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
