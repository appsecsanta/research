from flask import Flask, request, redirect, url_for, render_template, make_response
from flask_sqlalchemy import SQLAlchemy
import uuid
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    remember_token = db.Column(db.String(120), nullable=True)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        remember = 'remember' in request.form

        user = User.query.filter_by(username=username, password=password).first()

        if user:
            response = make_response(redirect(url_for('dashboard')))
            if remember:
                token = str(uuid.uuid4())
                user.remember_token = token
                db.session.commit()
                expires = datetime.now() + timedelta(days=30)
                response.set_cookie('remember_token', token, expires=expires)
            return response
        else:
            return "Invalid username or password", 401
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    remember_token = request.cookies.get('remember_token')
    if remember_token:
        user = User.query.filter_by(remember_token=remember_token).first()
        if user:
            return f"Welcome back, {user.username}!"
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    response = make_response(redirect(url_for('login')))
    response.set_cookie('remember_token', '', expires=0)
    return response

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
