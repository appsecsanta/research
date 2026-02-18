from flask import Flask, request, make_response
import secrets
import datetime

app = Flask(__name__)

def generate_session_token():
    return secrets.token_hex(32)

@app.route('/login', methods=['POST'])
def login():
    # Assume authentication is successful and user_id is obtained
    # In production, replace with actual authentication logic
    user_id = request.form.get('username')  # Example: from form data

    if not user_id:  # Basic validation
        return "Invalid credentials", 401

    session_token = generate_session_token()
    cookie_value = f"{user_id}:{session_token}"

    response = make_response("Login successful")
    response.set_cookie(
        'remember_me',
        cookie_value,
        max_age=30 * 24 * 60 * 60,  # 30 days
        httponly=True,
        secure=True,  # Use secure=True in production with HTTPS
        samesite='Lax'
    )
    return response
