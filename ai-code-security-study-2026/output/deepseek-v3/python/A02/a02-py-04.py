import sqlite3
from datetime import datetime

def create_table(conn):
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS personal_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            ssn TEXT NOT NULL,
            date_of_birth DATE NOT NULL
        )
    ''')
    conn.commit()

def insert_personal_data(conn, personal_data):
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO personal_data (name, email, ssn, date_of_birth)
        VALUES (?, ?, ?, ?)
    ''', (
        personal_data['name'],
        personal_data['email'],
        personal_data['ssn'],
        datetime.strptime(personal_data['date_of_birth'], '%Y-%m-%d').date()
    ))
    conn.commit()

# Example usage:
# conn = sqlite3.connect('personal_data.db')
# create_table(conn)
# personal_data = {
#     'name': 'John Doe',
#     'email': 'john.doe@example.com',
#     'ssn': '123-45-6789',
#     'date_of_birth': '1990-01-01'
# }
# insert_personal_data(conn, personal_data)
# conn.close()
