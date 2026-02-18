import sqlite3
import re
import hashlib
import os
from datetime import datetime
from typing import Optional


DB_PATH = "user_data.db"


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Create and return a database connection."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def create_table(db_path: str = DB_PATH) -> None:
    """Create the users table if it doesn't exist."""
    conn = get_connection(db_path)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                ssn_hash TEXT NOT NULL,
                ssn_last_four TEXT NOT NULL,
                date_of_birth TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_ssn_hash ON users(ssn_hash)
        """)
        conn.commit()
    finally:
        conn.close()


def _validate_email(email: str) -> bool:
    """Validate email format."""
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def _validate_ssn(ssn: str) -> bool:
    """Validate SSN format (XXX-XX-XXXX or XXXXXXXXX)."""
    cleaned = ssn.replace("-", "")
    return bool(re.match(r"^\d{9}$", cleaned))


def _validate_date_of_birth(dob: str) -> bool:
    """Validate date of birth format (YYYY-MM-DD)."""
    try:
        parsed = datetime.strptime(dob, "%Y-%m-%d")
        if parsed > datetime.now():
            return False
        if parsed.year < 1900:
            return False
        return True
    except ValueError:
        return False


def _validate_name(name: str) -> bool:
    """Validate that name is non-empty and reasonable."""
    if not name or not name.strip():
        return False
    if len(name.strip()) > 255:
        return False
    return True


def _hash_ssn(ssn: str) -> str:
    """Hash SSN with a salt for secure storage."""
    cleaned = ssn.replace("-", "")
    salt = os.environ.get("SSN_SALT", "default-change-in-production")
    salted = f"{salt}{cleaned}".encode("utf-8")
    return hashlib.sha256(salted).hexdigest()


def _get_ssn_last_four(ssn: str) -> str:
    """Extract last four digits of SSN."""
    cleaned = ssn.replace("-", "")
    return cleaned[-4:]


def validate_user_data(user_data: dict) -> list[str]:
    """Validate all fields in user data. Returns list of error messages."""
    errors = []

    required_fields = ["name", "email", "ssn", "date_of_birth"]
    for field in required_fields:
        if field not in user_data:
            errors.append(f"Missing required field: {field}")

    if errors:
        return errors

    if not _validate_name(user_data["name"]):
        errors.append("Invalid name: must be non-empty and under 255 characters")

    if not _validate_email(user_data["email"]):
        errors.append(f"Invalid email format: {user_data['email']}")

    if not _validate_ssn(user_data["ssn"]):
        errors.append("Invalid SSN format: expected XXX-XX-XXXX or XXXXXXXXX")

    if not _validate_date_of_birth(user_data["date_of_birth"]):
        errors.append("Invalid date of birth: expected YYYY-MM-DD, must be in the past")

    return errors


def store_user(user_data: dict, db_path: str = DB_PATH) -> int:
    """
    Validate and store user personal data in the database.

    Args:
        user_data: Dictionary with keys 'name', 'email', 'ssn', 'date_of_birth'.
            - name (str): Full name
            - email (str): Email address
            - ssn (str): Social Security Number (XXX-XX-XXXX or XXXXXXXXX)
            - date_of_birth (str): Date of birth (YYYY-MM-DD)
        db_path: Path to the SQLite database file.

    Returns:
        The row ID of the inserted record.

    Raises:
        ValueError: If validation fails.
        sqlite3.IntegrityError: If email already exists.
    """
    errors = validate_user_data(user_data)
    if errors:
        raise ValueError(f"Validation failed: {'; '.join(errors)}")

    create_table(db_path)

    ssn_hash = _hash_ssn(user_data["ssn"])
    ssn_last_four = _get_ssn_last_four(user_data["ssn"])
    name = user_data["name"].strip()
    email = user_data["email"].strip().lower()
    dob = user_data["date_of_birth"].strip()

    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            """
            INSERT INTO users (name, email, ssn_hash, ssn_last_four, date_of_birth)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name, email, ssn_hash, ssn_last_four, dob),
        )
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError as e:
        conn.rollback()
        if "email" in str(e).lower() or "unique" in str(e).lower():
            raise sqlite3.IntegrityError(
                f"A user with email '{email}' already exists"
            ) from e
        raise
    finally:
        conn.close()


def get_user_by_email(email: str, db_path: str = DB_PATH) -> Optional[dict]:
    """Retrieve a user record by email address."""
    conn = get_connection(db_path)
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT id, name, email, ssn_last_four, date_of_birth, created_at, updated_at "
            "FROM users WHERE email = ?",
            (email.strip().lower(),),
        )
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    finally:
        conn.close()


def get_user_by_id(user_id: int, db_path: str = DB_PATH) -> Optional[dict]:
    """Retrieve a user record by ID."""
    conn = get_connection(db_path)
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT id, name, email, ssn_last_four, date_of_birth, created_at, updated_at "
            "FROM users WHERE id = ?",
            (user_id,),
        )
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    finally:
        conn.close()


if __name__ == "__main__":
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        test_db = tmp.name

    try:
        create_table(test_db)

        user = {
            "name": "Jane Doe",
            "email": "jane.doe@example.com",
            "ssn": "123-45-6789",
            "date_of_birth": "1990-05-15",
        }

        row_id = store_user(user, db_path=test_db)
        print(f"User stored with ID: {row_id}")

        retrieved = get_user_by_email("jane.doe@example.com", db_path=test_db)
        print(f"Retrieved user: {retrieved}")

        # Demonstrate validation
        invalid_user = {
            "name": "",
            "email": "not-an-email",
            "ssn": "123",
            "date_of_birth": "not-a-date",
        }
        try:
            store_user(invalid_user, db_path=test_db)
        except ValueError as e:
            print(f"Validation error (expected): {e}")

        # Demonstrate duplicate email handling
        try:
            store_user(user, db_path=test_db)
        except sqlite3.IntegrityError as e:
            print(f"Integrity error (expected): {e}")

    finally:
        os.unlink(test_db)
