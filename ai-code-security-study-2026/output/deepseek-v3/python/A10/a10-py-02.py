from flask import Flask, request, jsonify
import sqlite3
import requests

app = Flask(__name__)

DATABASE = 'webhooks.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db_connection() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS webhooks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL UNIQUE
            )
        ''')
        conn.commit()

@app.route('/api/webhooks/register', methods=['POST'])
def register_webhook():
    data = request.get_json()
    url = data.get('url')
    if not url:
        return jsonify({"error": "URL is required"}), 400

    try:
        with get_db_connection() as conn:
            conn.execute('INSERT INTO webhooks (url) VALUES (?)', (url,))
            conn.commit()
        return jsonify({"message": "Webhook registered successfully"}), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": "URL already registered"}), 409

def notify_webhooks(event_data):
    with get_db_connection() as conn:
        webhooks = conn.execute('SELECT url FROM webhooks').fetchall()
    
    for webhook in webhooks:
        try:
            requests.post(webhook['url'], json=event_data, timeout=5)
        except requests.RequestException as e:
            print(f"Failed to notify {webhook['url']}: {e}")

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
