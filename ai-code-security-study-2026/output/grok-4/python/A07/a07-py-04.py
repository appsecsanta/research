from flask import Flask, request, render_template_string, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Replace with a secure key in production

DB_NAME = 'login.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE NOT NULL,
                  password TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS login_attempts
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT NOT NULL,
                  timestamp DATETIME NOT NULL,
                  success BOOLEAN NOT NULL,
                  ip TEXT NOT NULL)''')
    # Add a test user if not exists
    test_username = 'admin'
    test_password = generate_password_hash('password')
    c.execute("INSERT OR IGNORE INTO users (username, password) VALUES (?, ?)",
              (test_username, test_password))
    conn.commit()
    conn.close()

init_db()

def is_blocked(username):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    time_threshold = datetime.now() - timedelta(minutes=10)
    c.execute('''SELECT COUNT(*) FROM login_attempts
                 WHERE username = ? AND timestamp > ? AND success = 0''',
              (username, time_threshold))
    count = c.fetchone()[0]
    conn.close()
    return count >= 5

def log_attempt(username, success, ip):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''INSERT INTO login_attempts (username, timestamp, success, ip)
                 VALUES (?, ?, ?, ?)''',
              (username, datetime.now(), success, ip))
    conn.commit()
    conn.close()

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        ip = request.remote_addr

        if not username or not password:
            return "Missing username or password.", 400

        if is_blocked(username):
            return "Account temporarily blocked due to too many failed attempts. Try again later.", 403

        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT password FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user[0], password):
            log_attempt(username, True, ip)
            session['user'] = username
            return "Login successful!", 200
        else:
            log_attempt(username, False, ip)
            return "Invalid username or password.", 401

    # GET: Render login form
    html = '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Login</title>
    </head>
    <body>
        <h2>Login</h2>
        <form method="post">
            <label for="username">Username:</label>
            <input type="text" id="username" name="username" required><br><br>
            <label for="password">Password:</label>
            <input type="password" id="password" name="password" required><br><br>
            <input type="submit" value="Login">
        </form>
    </body>
    </html>
    '''
    return render_template_string(html)

if __name__ == '__main__':
    app.run(debug=True)
