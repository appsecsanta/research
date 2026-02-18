import logging
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)

# Configure logging
logging.basicConfig(filename='login_attempts.log', level=logging.INFO,
                    format='%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

# Database connection function
def get_db_connection():
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    return conn

# Initialize database (run this once to set up, or ensure it exists)
def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    ''')
    # Example user (for testing; remove in production or use proper user management)
    example_password_hash = generate_password_hash('password123')
    conn.execute('INSERT OR IGNORE INTO users (username, password_hash) VALUES (?, ?)',
                 ('admin', example_password_hash))
    conn.commit()
    conn.close()

# Call init_db() once; comment out after initial run
# init_db()

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or 'username' not in data or 'password' not in data:
        log_attempt(data.get('username', 'unknown'), request.remote_addr, 'failed', 'Missing credentials')
        return jsonify({'error': 'Missing username or password'}), 400

    username = data['username']
    password = data['password']
    ip_address = request.remote_addr

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()

    if user and check_password_hash(user['password_hash'], password):
        log_attempt(username, ip_address, 'success')
        return jsonify({'message': 'Login successful'}), 200
    else:
        log_attempt(username, ip_address, 'failed', 'Invalid credentials')
        return jsonify({'error': 'Invalid username or password'}), 401

def log_attempt(username, ip_address, status, reason=None):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    message = f"Login attempt: username={username}, ip={ip_address}, status={status}"
    if reason:
        message += f", reason={reason}"
    logging.info(message)

if __name__ == '__main__':
    app.run(debug=True)
