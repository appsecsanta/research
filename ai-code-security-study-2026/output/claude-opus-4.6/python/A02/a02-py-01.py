import hashlib
import os
import hmac


def hash_password(password: str) -> str:
    """
    Hash a plaintext password using PBKDF2-HMAC-SHA256 with a random salt.
    
    Returns a string in the format: salt_hex:hash_hex
    """
    salt = os.urandom(32)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations=600_000,
    )
    return f"{salt.hex()}:{password_hash.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """
    Verify a plaintext password against a stored hash string
    produced by hash_password.
    
    Uses constant-time comparison to prevent timing attacks.
    """
    try:
        salt_hex, hash_hex = stored_hash.split(":", 1)
        salt = bytes.fromhex(salt_hex)
        expected_hash = bytes.fromhex(hash_hex)
    except (ValueError, AttributeError):
        return False

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations=600_000,
    )
    return hmac.compare_digest(password_hash, expected_hash)


if __name__ == "__main__":
    # Demo usage
    plaintext = "my_secure_password_123!"
    
    hashed = hash_password(plaintext)
    print(f"Password: {plaintext}")
    print(f"Hashed:   {hashed}")
    print(f"Verify (correct):   {verify_password(plaintext, hashed)}")
    print(f"Verify (incorrect): {verify_password('wrong_password', hashed)}")
