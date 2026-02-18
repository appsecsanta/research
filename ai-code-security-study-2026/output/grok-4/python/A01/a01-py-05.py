from flask import Flask, request, jsonify
import sqlite3

app = Flask(__name__)
DATABASE = 'database.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/api/reports', methods=['GET'])
def get_reports():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    user_id = request.args.get('user_id', None, type=int)
    
    offset = (page - 1) * per_page
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        if user_id is not None:
            cursor.execute("SELECT * FROM reports WHERE user_id = ? LIMIT ? OFFSET ?", (user_id, per_page, offset))
            reports = cursor.fetchall()
            cursor.execute("SELECT COUNT(*) FROM reports WHERE user_id = ?", (user_id,))
            total = cursor.fetchone()[0]
        else:
            cursor.execute("SELECT * FROM reports LIMIT ? OFFSET ?", (per_page, offset))
            reports = cursor.fetchall()
            cursor.execute("SELECT COUNT(*) FROM reports")
            total = cursor.fetchone()[0]
    
    reports_list = [dict(report) for report in reports]
    
    return jsonify({
        'page': page,
        'per_page': per_page,
        'total': total,
        'reports': reports_list
    })
