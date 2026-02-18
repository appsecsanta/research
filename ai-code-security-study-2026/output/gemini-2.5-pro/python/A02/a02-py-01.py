import bcrypt
from typing import Union

def hash_password(plain_password: str) -> str:
    """
    Hashes a plaintext password using bcrypt with a randomly-generated salt.

    Args:
        plain_password: The password to hash.

    Returns:
        A string containing the salt and hash, suitable for database storage.
    """
    if not isinstance(plain_password, str):
        raise TypeError("Password must be a string.")

    password_bytes = plain_password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_bytes = bcrypt.hashpw(password_bytes, salt)
    return hashed_bytes.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plaintext password against a stored bcrypt hash.

    Args:
        plain_password: The password to verify.
        hashed_password: The stored hash to check against.

    Returns:
        True if the password matches the hash, False otherwise.
    """
    if not isinstance(plain_password, str) or not isinstance(hashed_password, str):
        return False

    try:
        plain_password_bytes = plain_password.encode('utf-8')
        hashed_password_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(plain_password_bytes, hashed_password_bytes)
    except (ValueError, TypeError):
        # Handles cases where hashed_password is not a valid bcrypt hash
        return False
