import sqlite3
from sqlite3 import Error
from datetime import datetime

def create_table(conn):
    create_table_sql = """
        CREATE TABLE IF NOT EXISTS personal_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            ssn TEXT NOT NULL,
            date_of_birth DATE NOT NULL
        );
    """
    try:
        c = conn.cursor()
        c.execute(create_table_sql)
    except Error as e:
        print(e)

def insert_data(conn, data):
    insert_data_sql = """
        INSERT INTO personal_data (name, email, ssn, date_of_birth)
        VALUES (?, ?, ?, ?);
    """
    try:
        c = conn.cursor()
        c.execute(insert_data_sql, (
            data['name'],
            data['email'],
            data['ssn'],
            datetime.strptime(data['date_of_birth'], '%Y-%m-%d').date()
        ))
        conn.commit()
        return c.lastrowid
    except Error as e:
        print(e)

def main():
    database = 'personal_data.db'
    conn = None
    try:
        conn = sqlite3.connect(database)
        print(f"Connected to SQLite Database {database}")
        create_table(conn)
        
        user_data = {
            'name': 'John Doe',
            'email': 'john@example.com',
            'ssn': '123-45-6789',
            'date_of_birth': '1990-01-01'
        }
        insert_data(conn, user_data)
    except Error as e:
        print(e)
    finally:
        if conn:
            conn.close()
            print("SQLite Connection is closed")

if __name__ == '__main__':
    main()
