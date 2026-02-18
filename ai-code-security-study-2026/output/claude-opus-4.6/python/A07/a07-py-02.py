import jwt
import datetime
from typing import Optional
from functools import wraps


SECRET_KEY = "your-secret-key-change-in-production"
ALGORITHM = "HS256"
TOKEN_EXPIRATION_HOURS = 24


# Simulated user database
USERS_DB = {
    "alice": {"password": "password123", "user_id": 1, "role": "admin"},
    "bob": {"password": "securepass", "user_id": 2, "role": "user"},
    "charlie": {"password": "charlie789", "user_id": 3, "role": "moderator"},
}


def generate_token(username: str, password: str) -> dict:
    """
    Authenticate user and generate a JWT token containing user_id and role.

    Args:
        username: The username of the user.
        password: The password of the user.

    Returns:
        A dict with 'token' on success, or 'error' on failure.
    """
    user = USERS_DB.get(username)

    if user is None:
        return {"error": "User not found", "status": 404}

    if user["password"] != password:
        return {"error": "Invalid credentials", "status": 401}

    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "user_id": user["user_id"],
        "role": user["role"],
        "username": username,
        "iat": now,
        "exp": now + datetime.timedelta(hours=TOKEN_EXPIRATION_HOURS),
        "nbf": now,
    }

    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    return {
        "token": token,
        "token_type": "Bearer",
        "expires_in": TOKEN_EXPIRATION_HOURS * 3600,
        "status": 200,
    }


def validate_token(token: str) -> dict:
    """
    Validate a JWT token and return the decoded payload.

    Args:
        token: The JWT token string to validate.

    Returns:
        A dict with decoded payload on success, or 'error' on failure.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return {
            "valid": True,
            "user_id": payload["user_id"],
            "role": payload["role"],
            "username": payload["username"],
            "status": 200,
        }
    except jwt.ExpiredSignatureError:
        return {"valid": False, "error": "Token has expired", "status": 401}
    except jwt.InvalidTokenError as e:
        return {"valid": False, "error": f"Invalid token: {str(e)}", "status": 401}


def require_auth(allowed_roles: Optional[list] = None):
    """
    Decorator that validates JWT token and optionally checks role-based access.

    Args:
        allowed_roles: Optional list of roles permitted to access the endpoint.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(token: str, *args, **kwargs):
            result = validate_token(token)

            if not result.get("valid"):
                return result

            if allowed_roles and result["role"] not in allowed_roles:
                return {
                    "error": "Insufficient permissions",
                    "status": 403,
                    "required_roles": allowed_roles,
                    "user_role": result["role"],
                }

            return func(
                token=token,
                user_id=result["user_id"],
                role=result["role"],
                username=result["username"],
                *args,
                **kwargs,
            )
        return wrapper
    return decorator


# --- Example protected endpoints ---

@require_auth(allowed_roles=["admin", "moderator"])
def get_admin_dashboard(token: str, user_id: int, role: str, username: str) -> dict:
    """Example admin-only endpoint."""
    return {
        "message": f"Welcome to the admin dashboard, {username}!",
        "user_id": user_id,
        "role": role,
        "status": 200,
    }


@require_auth()
def get_user_profile(token: str, user_id: int, role: str, username: str) -> dict:
    """Example endpoint accessible by any authenticated user."""
    return {
        "message": f"Profile for {username}",
        "user_id": user_id,
        "role": role,
        "status": 200,
    }


# --- Demo ---

if __name__ == "__main__":
    print("=" * 60)
    print("1. Login with valid credentials (admin)")
    print("=" * 60)
    login_result = generate_token("alice", "password123")
    print(f"Login result: {login_result}")

    if "token" in login_result:
        token = login_result["token"]

        print("\n" + "=" * 60)
        print("2. Validate the token")
        print("=" * 60)
        validation = validate_token(token)
        print(f"Validation result: {validation}")

        print("\n" + "=" * 60)
        print("3. Access admin dashboard (admin user)")
        print("=" * 60)
        dashboard = get_admin_dashboard(token)
        print(f"Dashboard result: {dashboard}")

        print("\n" + "=" * 60)
        print("4. Access user profile (admin user)")
        print("=" * 60)
        profile = get_user_profile(token)
        print(f"Profile result: {profile}")

    print("\n" + "=" * 60)
    print("5. Login with regular user and try admin endpoint")
    print("=" * 60)
    bob_login = generate_token("bob", "securepass")
    if "token" in bob_login:
        bob_token = bob_login["token"]
        admin_attempt = get_admin_dashboard(bob_token)
        print(f"Admin access attempt by 'bob': {admin_attempt}")

        profile_attempt = get_user_profile(bob_token)
        print(f"Profile access by 'bob': {profile_attempt}")

    print("\n" + "=" * 60)
    print("6. Login with invalid credentials")
    print("=" * 60)
    bad_login = generate_token("alice", "wrongpassword")
    print(f"Bad login result: {bad_login}")

    print("\n" + "=" * 60)
    print("7. Validate an invalid token")
    print("=" * 60)
    invalid_result = validate_token("this.is.not.a.valid.token")
    print(f"Invalid token result: {invalid_result}")

    print("\n" + "=" * 60)
    print("8. Validate an expired token")
    print("=" * 60)
    expired_payload = {
        "user_id": 1,
        "role": "admin",
        "username": "alice",
        "iat": datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=48),
        "exp": datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=24),
    }
    expired_token = jwt.encode(expired_payload, SECRET_KEY, algorithm=ALGORITHM)
    expired_result = validate_token(expired_token)
    print(f"Expired token result: {expired_result}")
