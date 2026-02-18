import os
import sqlite3
import uuid
from datetime import datetime
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Create uploads directory if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize SQLite database
def init_db():
    conn = sqlite3.connect('uploads.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_filename TEXT NOT NULL,
            stored_filename TEXT NOT NULL,
            upload_date TEXT NOT NULL,
            uploader TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    uploader = request.form.get('uploader', 'anonymous')
    if file:
        original_filename = secure_filename(file.filename)
        stored_filename = f"{uuid.uuid4()}_{original_filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], stored_filename)
        file.save(file_path)
        
        # Save metadata to database
        conn = sqlite3.connect('uploads.db')
        cursor = conn.cursor()
        upload_date = datetime.now().isoformat()
        cursor.execute('''
            INSERT INTO files (original_filename, stored_filename, upload_date, uploader)
            VALUES (?, ?, ?, ?)
        ''', (original_filename, stored_filename, upload_date, uploader))
        conn.commit()
        conn.close()
        
        file_url = f"/uploads/{stored_filename}"
        return jsonify({'url': file_url}), 200

if __name__ == '__main__':
    app.run(debug=True)
