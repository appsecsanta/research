from flask import Flask, request, jsonify, session
import sqlite3

app = Flask(__name__)
app.secret_key = 'your_secret_key'

def verify_credentials(username, password):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT name FROM users WHERE username = ? AND password = ?', (username, password))
    user = cursor.fetchone()
    conn.close()
    return user

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    user = verify_credentials(username, password)
    
    if user:
        session['username'] = username
        return jsonify({"message": "Login successful", "name": user[0]}), 200
    else:
        return jsonify({"message": "Invalid credentials"}), 401

if __name__ == '__main__':
    app.run(debug=True)
