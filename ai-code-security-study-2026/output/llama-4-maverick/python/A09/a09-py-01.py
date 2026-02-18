from flask import Flask, request, jsonify
import sqlite3
import logging
from werkzeug.security import check_password_hash
from datetime import datetime

app = Flask(__name__)

# Set up logging
logging.basicConfig(filename='login_attempts.log', level=logging.INFO, format='%(asctime)s - %(message)s')

# Connect to SQLite database
def get_db_connection():
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    if not data or 'username' not in data or 'password' not in data:
        logging.info(f'Failed login attempt: missing credentials')
        return jsonify({'error': 'Missing username or password'}), 400

    username = data['username']
    password = data['password']

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()

    if user and check_password_hash(user['password'], password):
        logging.info(f'Successful login attempt: username={username}, ip={request.remote_addr}')
        return jsonify({'message': 'Login successful'}), 200
    else:
        logging.info(f'Failed login attempt: username={username}, ip={request.remote_addr}')
        return jsonify({'error': 'Invalid username or password'}), 401

if __name__ == '__main__':
    app.run(debug=True)
