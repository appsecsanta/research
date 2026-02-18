from flask import Flask, request, jsonify
import sqlite3
import uuid
import datetime
import hashlib

app = Flask(__name__)
DATABASE = 'database.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS reset_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            token TEXT NOT NULL,
            expiration TIMESTAMP NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

@app.route('/forgot-password', methods=['POST'])
def forgot_password():
    email = request.json.get('email')
    if not email:
        return jsonify({"error": "Email is required"}), 400

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    if not user:
        return jsonify({"error": "User not found"}), 404

    token = str(uuid.uuid4())
    expiration = datetime.datetime.now() + datetime.timedelta(hours=1)
    conn.execute('INSERT INTO reset_tokens (email, token, expiration) VALUES (?, ?, ?)',
                 (email, token, expiration))
    conn.commit()
    conn.close()

    return jsonify({"message": "Reset token generated", "token": token}), 200

@app.route('/reset-password', methods=['POST'])
def reset_password():
    token = request.json.get('token')
    new_password = request.json.get('new_password')
    if not token or not new_password:
        return jsonify({"error": "Token and new password are required"}), 400

    conn = get_db_connection()
    reset_token = conn.execute('SELECT * FROM reset_tokens WHERE token = ?', (token,)).fetchone()
    if not reset_token:
        return jsonify({"error": "Invalid token"}), 400

    if datetime.datetime.now() > datetime.datetime.fromisoformat(reset_token['expiration']):
        return jsonify({"error": "Token has expired"}), 400

    hashed_password = hash_password(new_password)
    conn.execute('UPDATE users SET password = ? WHERE email = ?',
                 (hashed_password, reset_token['email']))
    conn.execute('DELETE FROM reset_tokens WHERE token = ?', (token,))
    conn.commit()
    conn.close()

    return jsonify({"message": "Password reset successfully"}), 200

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
