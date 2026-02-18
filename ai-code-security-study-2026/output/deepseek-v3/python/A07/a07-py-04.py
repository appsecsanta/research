from flask import Flask, request, jsonify
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)
DATABASE = 'login_attempts.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS login_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            attempts INTEGER DEFAULT 0,
            last_attempt TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def is_user_blocked(username):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM login_attempts WHERE username = ?', (username,)).fetchone()
    conn.close()

    if user and user['attempts'] >= 3:
        last_attempt = datetime.strptime(user['last_attempt'], '%Y-%m-%d %H:%M:%S')
        if datetime.now() - last_attempt < timedelta(minutes=5):
            return True
    return False

def update_login_attempt(username, success):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM login_attempts WHERE username = ?', (username,)).fetchone()

    if user:
        if success:
            conn.execute('UPDATE login_attempts SET attempts = 0 WHERE username = ?', (username,))
        else:
            conn.execute('UPDATE login_attempts SET attempts = attempts + 1, last_attempt = ? WHERE username = ?', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), username))
    else:
        conn.execute('INSERT INTO login_attempts (username, attempts, last_attempt) VALUES (?, ?, ?)', (username, 1 if not success else 0, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

    conn.commit()
    conn.close()

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if is_user_blocked(username):
        return jsonify({'message': 'Account temporarily locked. Try again later.'}), 403

    # Replace with actual authentication logic
    if username == 'admin' and password == 'password':
        update_login_attempt(username, True)
        return jsonify({'message': 'Login successful'}), 200
    else:
        update_login_attempt(username, False)
        return jsonify({'message': 'Invalid username or password'}), 401

if __name__ == '__main__':
    app.run(debug=True)
