import secrets
import hashlib
import datetime
from typing import Optional

class PasswordResetToken:
    def __init__(self, db):
        self.db = db

    def generate_token(self, email: str) -> str:
        token = secrets.token_urlsafe(32)
        hashed_token = self._hash_token(token)
        expiration_timestamp = datetime.datetime.now() + datetime.timedelta(hours=1)
        self.db.store_password_reset_token(email, hashed_token, expiration_timestamp)
        return token

    def validate_token(self, email: str, token: str) -> bool:
        stored_hashed_token, expiration_timestamp = self.db.get_password_reset_token(email)
        if stored_hashed_token is None or expiration_timestamp is None:
            return False
        if expiration_timestamp < datetime.datetime.now():
            return False
        hashed_token = self._hash_token(token)
        return stored_hashed_token == hashed_token

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()


class Database:
    def __init__(self):
        self.password_reset_tokens = {}

    def store_password_reset_token(self, email: str, hashed_token: str, expiration_timestamp: datetime.datetime):
        self.password_reset_tokens[email] = (hashed_token, expiration_timestamp)

    def get_password_reset_token(self, email: str) -> tuple[Optional[str], Optional[datetime.datetime]]:
        return self.password_reset_tokens.get(email, (None, None))


def main():
    db = Database()
    password_reset_token = PasswordResetToken(db)
    email = "user@example.com"
    token = password_reset_token.generate_token(email)
    print(f"Generated token: {token}")
    print(f"Is token valid? {password_reset_token.validate_token(email, token)}")


if __name__ == "__main__":
    main()
