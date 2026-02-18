import jwt
from datetime import datetime, timedelta

secret_key = "your-secret-key"

def generate_jwt_token(user_id: int, user_role: str) -> str:
    payload = {
        "user_id": user_id,
        "user_role": user_role,
        "exp": datetime.utcnow() + timedelta(hours=1)
    }
    return jwt.encode(payload, secret_key, algorithm="HS256")

def validate_jwt_token(token: str) -> dict:
    try:
        return jwt.decode(token, secret_key, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired")
    except jwt.InvalidTokenError:
        raise ValueError("Invalid token")
