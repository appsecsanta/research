from flask import Flask, jsonify, g
import sqlite3
import json

app = Flask(__name__)

# Configuration
DATABASE = 'users.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

@app.route('/api/users/<int:user_id>/profile', methods=['GET'])
def get_user_profile(user_id):
    user = query_db('SELECT email, phone_number, address FROM users WHERE id = ?', [user_id], one=True)
    if user is None:
        return jsonify({'error': 'User not found'}), 404
    return jsonify({
        'email': user['email'],
        'phone_number': user['phone_number'],
        'address': user['address']
    })

if __name__ == '__main__':
    app.run(debug=True)
