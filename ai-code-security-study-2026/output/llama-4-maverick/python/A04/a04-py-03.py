from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
import os
import sqlite3
from datetime import datetime
import uuid

app = Flask(__name__)

# Configuration
UPLOAD_FOLDER = 'uploads'
DATABASE_NAME = 'file_metadata.db'
ALLOWED_EXTENSIONS = set(['txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'])

# Create upload directory if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Create database if it doesn't exist
conn = sqlite3.connect(DATABASE_NAME)
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS file_metadata
    (id TEXT PRIMARY KEY, original_filename TEXT, upload_date TEXT, uploader TEXT, file_url TEXT)
''')
conn.commit()
conn.close()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_file_metadata(file_id, original_filename, uploader, file_url):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO file_metadata (id, original_filename, upload_date, uploader, file_url)
        VALUES (?, ?, ?, ?, ?)
    ''', (file_id, original_filename, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), uploader, file_url))
    conn.commit()
    conn.close()

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file and allowed_file(file.filename):
        file_id = str(uuid.uuid4())
        filename = secure_filename(file.filename)
        file_ext = filename.rsplit('.', 1)[1].lower()
        new_filename = f'{file_id}.{file_ext}'
        file.save(os.path.join(UPLOAD_FOLDER, new_filename))
        uploader = request.form.get('uploader', 'anonymous')
        file_url = f'/uploads/{new_filename}'
        save_file_metadata(file_id, filename, uploader, file_url)
        return jsonify({'file_url': file_url}), 201

if __name__ == '__main__':
    app.run(debug=True)
