import sqlite3
import logging
from typing import Dict, Any

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

DB_FILE = "user_data.db"

def initialize_database(db_path: str = DB_FILE) -> None:
    """
    Initializes the SQLite database and creates the personal_data table if it
    does not exist.

    The table schema includes an auto-incrementing primary key, and unique
    constraints on email and SSN to prevent duplicate entries.

    Args:
        db_path (str): The file path for the SQLite database.
    """
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS personal_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE,
                    ssn TEXT NOT NULL UNIQUE,
                    date_of_birth TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            logging.info(f"Database '{db_path}' initialized successfully.")
    except sqlite3.Error as e:
        logging.error(f"Database error during initialization: {e}")
        raise

def store_personal_data(user_data: Dict[str, str], db_path: str = DB_FILE) -> int:
    """
    Stores a user's personal data dictionary into the SQLite database.

    This function uses parameterized queries to prevent SQL injection.

    Args:
        user_data (Dict[str, str]): A dictionary containing the user's data.
            Expected keys: 'name', 'email', 'ssn', 'date_of_birth'.
        db_path (str): The file path for the SQLite database.

    Returns:
        int: The row ID of the newly inserted record.

    Raises:
        sqlite3.IntegrityError: If the email or SSN already exists in the database.
        KeyError: If a required key is missing from the user_data dictionary.
        sqlite3.Error: For other database-related errors.
    """
    required_keys = {'name', 'email', 'ssn', 'date_of_birth'}
    if not required_keys.issubset(user_data.keys()):
        missing_keys = required_keys - user_data.keys()
        raise KeyError(f"Missing required keys in user_data: {missing_keys}")

    sql = """
        INSERT INTO personal_data (name, email, ssn, date_of_birth)
        VALUES (:name, :email, :ssn, :date_of_birth)
    """

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(sql, user_data)
            conn.commit()
            new_id = cursor.lastrowid
            logging.info(f"Successfully stored data for user '{user_data['name']}' with ID {new_id}.")
            return new_id
    except sqlite3.IntegrityError as e:
        logging.error(f"Integrity error: {e}. Likely a duplicate email or SSN.")
        raise
    except sqlite3.Error as e:
        logging.error(f"Database error while storing data: {e}")
        raise


if __name__ == '__main__':
    # Example Usage

    # 1. Initialize the database and create the table
    initialize_database()

    # 2. Define some sample user data
    user1_data = {
        "name": "John Doe",
        "email": "john.doe@example.com",
        "ssn": "000-00-0001",
        "date_of_birth": "1990-05-15"
    }

    user2_data = {
        "name": "Jane Smith",
        "email": "jane.smith@example.com",
        "ssn": "000-00-0002",
        "date_of_birth": "1985-11-22"
    }

    # 3. Store the data
    try:
        user1_id = store_personal_data(user1_data)
        print(f"User 1 stored with ID: {user1_id}")
    except (sqlite3.IntegrityError, KeyError) as e:
        print(f"Could not store User 1: {e}")

    try:
        user2_id = store_personal_data(user2_data)
        print(f"User 2 stored with ID: {user2_id}")
    except (sqlite3.IntegrityError, KeyError) as e:
        print(f"Could not store User 2: {e}")

    # 4. Attempt to store a duplicate user (will raise an IntegrityError)
    print("\nAttempting to store a user with a duplicate email...")
    duplicate_user_data = {
        "name": "John Doe Clone",
        "email": "john.doe@example.com",  # Duplicate email
        "ssn": "000-00-0003",
        "date_of_birth": "1990-05-15"
    }
    try:
        store_personal_data(duplicate_user_data)
    except sqlite3.IntegrityError as e:
        print(f"Caught expected error: {e}")

    # 5. Attempt to store data with a missing key (will raise a KeyError)
    print("\nAttempting to store a user with missing data...")
    incomplete_user_data = {
        "name": "Incomplete User",
        "email": "incomplete@example.com",
        # Missing 'ssn' and 'date_of_birth'
    }
    try:
        store_personal_data(incomplete_user_data)
    except KeyError as e:
        print(f"Caught expected error: {e}")
