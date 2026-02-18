import secrets
from datetime import datetime, timedelta
from typing import Optional

# Mock database for demonstration purposes
mock_db = {}

def generate_reset_token(email: str, expiration_minutes: int = 30) -> str:
    token = secrets.token_urlsafe(32)
    expiration_time = datetime.utcnow() + timedelta(minutes=expiration_minutes)
    mock_db[token] = {
        'email': email,
        'expiration_time': expiration_time
    }
    return token

def validate_reset_token(token: str) -> Optional[str]:
    if token in mock_db:
        token_data = mock_db[token]
        if datetime.utcnow() <= token_data['expiration_time']:
            return token_data['email']
        else:
            del mock_db[token]
    return None
