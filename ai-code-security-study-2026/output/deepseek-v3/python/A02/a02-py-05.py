from flask import Flask, request, make_response
from datetime import datetime, timedelta
import secrets

app = Flask(__name__)

@app.route('/login', methods=['POST'])
def login():
    user_id = request.form.get('user_id')
    session_token = secrets.token_hex(16)
    
    response = make_response("Logged in successfully")
    
    expires = datetime.now() + timedelta(days=30)
    response.set_cookie(
        'remember_me',
        value=f'{user_id}:{session_token}',
        expires=expires,
        httponly=True,
        secure=True
    )
    
    return response

if __name__ == '__main__':
    app.run(debug=True)
