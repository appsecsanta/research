import sqlite3
from flask import Flask, jsonify, request

app = Flask(__name__)
DATABASE = 'database.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db_connection() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                email TEXT NOT NULL
            )
        ''')
        conn.commit()

@app.route('/admin/users', methods=['GET'])
def list_users():
    conn = get_db_connection()
    users = conn.execute('SELECT * FROM users').fetchall()
    conn.close()
    return jsonify([dict(user) for user in users])

@app.route('/admin/users/<int:id>/delete', methods=['POST'])
def delete_user(id):
    conn = get_db_connection()
    cursor = conn.execute('DELETE FROM users WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    if cursor.rowcount == 0:
        return jsonify({'error': 'User not found'}), 404
    return jsonify({'message': 'User deleted'}), 200

@app.route('/admin/stats', methods=['GET'])
def stats():
    conn = get_db_connection()
    total_users = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    conn.close()
    return jsonify({'total_users': total_users})

if __name__ == '__main__':
    init_db()
    app.run()
