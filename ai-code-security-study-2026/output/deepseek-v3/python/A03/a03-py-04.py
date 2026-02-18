from flask import Flask, request, render_template
import sqlite3

app = Flask(__name__)

DATABASE = 'feedback.db'

def init_db():
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                message TEXT NOT NULL
            )
        ''')
        conn.commit()

@app.route('/api/feedback', methods=['POST'])
def submit_feedback():
    name = request.form.get('name')
    message = request.form.get('message')
    
    if not name or not message:
        return "Name and message are required", 400
    
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO feedback (name, message) VALUES (?, ?)', (name, message))
        conn.commit()
    
    return "Feedback submitted successfully", 201

@app.route('/feedback', methods=['GET'])
def show_feedback():
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT name, message FROM feedback')
        feedback_entries = cursor.fetchall()
    
    return render_template('feedback.html', feedback_entries=feedback_entries)

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
