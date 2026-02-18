import sqlite3
import json
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# Database setup
conn = sqlite3.connect('webhooks.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS webhooks
    (id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT NOT NULL)
''')

conn.commit()

def register_webhook(url):
    cursor.execute('INSERT INTO webhooks (url) VALUES (?)', (url,))
    conn.commit()

def get_registered_webhooks():
    cursor.execute('SELECT url FROM webhooks')
    return [row[0] for row in cursor.fetchall()]

def send_webhook(event_data):
    registered_webhooks = get_registered_webhooks()
    for webhook_url in registered_webhooks:
        try:
            requests.post(webhook_url, json=event_data)
        except requests.RequestException as e:
            print(f'Error sending webhook to {webhook_url}: {e}')

@app.route('/api/webhooks/register', methods=['POST'])
def register_webhook_endpoint():
    data = request.json
    if 'url' not in data:
        return jsonify({'error': 'Missing required field: url'}), 400
    register_webhook(data['url'])
    return jsonify({'message': 'Webhook registered successfully'}), 201

# Example usage:
if __name__ == '__main__':
    # Register a webhook
    # curl -X POST -H "Content-Type: application/json" -d '{"url": "http://example.com/webhook"}' http://localhost:5000/api/webhooks/register
    
    # Send a webhook event
    event_data = {'event': 'example_event', 'data': 'example_data'}
    send_webhook(event_data)
    
    app.run(debug=True)
