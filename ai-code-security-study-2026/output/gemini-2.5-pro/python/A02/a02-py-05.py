import os
import secrets
from datetime import datetime, timedelta, timezone

from flask import Flask, jsonify, make_response, request
from werkzeug.security import check_password_hash, generate_password_hash

# --- Application Setup ---
app = Flask(__name__)
# In a real app, this should be loaded from a secure configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(16))


# --- Models & Data (In-memory for demonstration) ---
# In a real application, this would be a database model (e.g., using SQLAlchemy)
USERS = {
    "1": {
        "id": "1",
        "username": "testuser",
        "password_hash": generate_password_hash("strongpassword123")
    }
}

# In a real application, you would store session tokens in a database or cache
# to validate them and allow for revocation.
SESSIONS = {}


# --- Authentication Logic ---
def authenticate_user(username, password):
    """
    Authenticates a user. In a real app, this would query a database.
    Returns the user object on success, None on failure.
    """
    user = next((u for u in USERS.values() if u['username'] == username), None)
    if user and check_password_hash(user['password_hash'], password):
        return user
    return None


# --- Endpoint Definition ---
@app.route('/login', methods=['POST'])
def login():
    """
    Handles user login, setting a 'remember me' cookie on success.
    Expects a JSON body with 'username' and 'password'.
    """
    data = request.get_json()
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({"error": "Username and password are required"}), 400

    username = data['username']
    password = data['password']

    user = authenticate_user(username, password)

    if not user:
        return jsonify({"error": "Invalid credentials"}), 401

    # --- Cookie Creation ---
    user_id = user['id']
    # Generate a secure, random token for the session
    session_token = secrets.token_hex(16)

    # Store the session token server-side (in-memory for this example)
    expires_at = datetime.now(timezone.utc) + timedelta(days=30)
    SESSIONS[session_token] = {
        "user_id": user_id,
        "expires_at": expires_at
    }

    cookie_value = f"{user_id}:{session_token}"

    response = make_response(jsonify({
        "message": "Login successful",
        "user_id": user_id
    }))

    response.set_cookie(
        'remember_me_token',
        value=cookie_value,
        expires=expires_at,
        httponly=True,  # Prevents client-side JavaScript from accessing the cookie
        secure=request.is_secure,  # Send cookie only over HTTPS in production
        samesite='Lax'  # Provides protection against CSRF attacks
    )

    return response


if __name__ == '__main__':
    # Note: For production, use a proper WSGI server like Gunicorn or uWSGI.
    # The development server is not suitable for production use.
    # Example: gunicorn --bind 0.0.0.0:8000 myapp:app
    app.run(debug=True, port=5001)
