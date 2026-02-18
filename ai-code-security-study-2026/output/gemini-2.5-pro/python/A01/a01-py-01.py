import sqlite3
import os
from flask import Flask, jsonify, g

# --- Configuration ---
DATABASE = 'user_profiles.db'
# Set the base directory of the application
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, DATABASE)


# --- Flask App Initialization ---
app = Flask(__name__)
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True


# --- Database Setup and Teardown ---
def init_db():
    """Initializes the database and populates it with sample data if it doesn't exist."""
    if os.path.exists(DB_PATH):
        return

    print(f"Creating and seeding database at {DB_PATH}...")
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL UNIQUE,
                    phone_number TEXT,
                    address_line1 TEXT,
                    city TEXT,
                    state TEXT,
                    zip_code TEXT
                );
            ''')
            cursor.execute('''
                INSERT INTO users (email, phone_number, address_line1, city, state, zip_code)
                VALUES (?, ?, ?, ?, ?, ?);
            ''', ('alice@example.com', '123-456-7890', '123 Main St', 'Anytown', 'CA', '12345'))
            cursor.execute('''
                INSERT INTO users (email, phone_number, address_line1, city, state, zip_code)
                VALUES (?, ?, ?, ?, ?, ?);
            ''', ('bob@example.com', '987-654-3210', '456 Oak Ave', 'Someville', 'NY', '54321'))
            conn.commit()
        print("Database created and seeded successfully.")
    except sqlite3.Error as e:
        print(f"Database error during initialization: {e}")
        # If initialization fails, remove the potentially corrupt file
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)


def get_db():
    """Opens a new database connection if there is none yet for the current application context."""
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row  # Allows accessing columns by name
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    """Closes the database again at the end of the request."""
    db = g.pop('db', None)
    if db is not None:
        db.close()


# --- API Endpoint ---
@app.route('/api/users/<int:user_id>/profile', methods=['GET'])
def get_user_profile(user_id: int):
    """
    Retrieves and returns the profile information for a specific user.
    """
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user_record = cursor.fetchone()

        if user_record is None:
            return jsonify({"error": "User not found"}), 404

        profile_data = {
            "id": user_record["id"],
            "email": user_record["email"],
            "phone_number": user_record["phone_number"],
            "address": {
                "line1": user_record["address_line1"],
                "city": user_record["city"],
                "state": user_record["state"],
                "zip_code": user_record["zip_code"]
            }
        }
        return jsonify(profile_data), 200

    except sqlite3.Error as e:
        app.logger.error(f"Database error on user profile fetch: {e}")
        return jsonify({"error": "A database error occurred"}), 500
    except Exception as e:
        app.logger.error(f"An unexpected error occurred: {e}")
        return jsonify({"error": "An internal server error occurred"}), 500


# --- Main Execution ---
if __name__ == '__main__':
    # Initialize the database before running the app
    init_db()
    # Example usage:
    # curl http://127.0.0.1:5000/api/users/1/profile
    # curl http://127.0.0.1:5000/api/users/2/profile
    # curl http://127.0.0.1:5000/api/users/99/profile
    app.run(host='0.0.0.0', port=5000, debug=True)
