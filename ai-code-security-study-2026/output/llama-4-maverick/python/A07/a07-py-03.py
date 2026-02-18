from flask import Flask, request, redirect, url_for, session, make_response
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    remember_me_tokens = db.relationship('RememberMeToken', backref='user', lazy=True)


class RememberMeToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    token = db.Column(db.String(36), unique=True, nullable=False)
    expires = db.Column(db.DateTime, nullable=False)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        remember_me = 'remember_me' in request.form

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            if remember_me:
                token = str(uuid.uuid4())
                expires = datetime.datetime.now() + datetime.timedelta(days=30)
                remember_me_token = RememberMeToken(user_id=user.id, token=token, expires=expires)
                db.session.add(remember_me_token)
                db.session.commit()
                resp = make_response(redirect(url_for('protected')))
                resp.set_cookie('remember_me', token, expires=expires)
                return resp
            return redirect(url_for('protected'))
    return '''
        <form method="post">
            <label>Username:</label><br>
            <input type="text" name="username"><br>
            <label>Password:</label><br>
            <input type="password" name="password"><br>
            <input type="checkbox" name="remember_me"> Remember me<br>
            <input type="submit" value="Login">
        </form>
    '''


@app.before_request
def before_request():
    if 'user_id' not in session:
        remember_me_token = request.cookies.get('remember_me')
        if remember_me_token:
            token = RememberMeToken.query.filter_by(token=remember_me_token).first()
            if token and token.expires > datetime.datetime.now():
                session['user_id'] = token.user_id
            else:
                resp = make_response(redirect(url_for('login')))
                resp.set_cookie('remember_me', '', expires=0)
                return resp


@app.route('/protected')
def protected():
    if 'user_id' in session:
        return 'Hello, user!'
    return redirect(url_for('login'))


@app.route('/logout')
def logout():
    if 'user_id' in session:
        del session['user_id']
    resp = make_response(redirect(url_for('login')))
    resp.set_cookie('remember_me', '', expires=0)
    return resp


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='test').first():
            user = User(username='test', password=generate_password_hash('test'))
            db.session.add(user)
            db.session.commit()
    app.run(debug=True)
