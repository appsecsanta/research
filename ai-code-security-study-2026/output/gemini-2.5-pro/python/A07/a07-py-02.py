import os
import jwt
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional

# It is strongly recommended to use a secure, randomly generated key and
# load it from environment variables or a secret management service.
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "a-secure-and-random-secret-key-for-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_SECONDS = 1800  # 30 minutes


def generate_jwt_token(user_id: int, user_role: str) -> str:
    """
    Generates a JWT token for a user.

    Args:
        user_id: The unique identifier for the user.
        user_role: The role assigned to the user (e.g., 'admin', 'user').

    Returns:
        A signed JWT token as a string.
    """
    payload = {
        "user_id": user_id,
        "role": user_role,
        "exp": datetime.now(timezone.utc) + timedelta(seconds=ACCESS_TOKEN_EXPIRE_SECONDS),
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token


def validate_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Validates a JWT token and returns its payload if successful.

    Args:
        token: The JWT token string to validate.

    Returns:
        A dictionary containing the token's payload if the token is valid
        (i.e., signature is correct and it has not expired), otherwise None.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None
