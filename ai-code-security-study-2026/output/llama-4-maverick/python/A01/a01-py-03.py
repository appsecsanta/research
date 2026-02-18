from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///admin_dashboard.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

    def __init__(self, username, email, password):
        self.username = username
        self.email = email
        self.password = generate_password_hash(password)

    def to_dict(self):
        return {"id": self.id, "username": self.username, "email": self.email}


@app.before_first_request
def create_tables():
    db.create_all()


@app.route("/admin/users", methods=["GET"])
def get_users():
    users = User.query.all()
    return jsonify([user.to_dict() for user in users])


@app.route("/admin/users/<int:user_id>/delete", methods=["DELETE"])
def delete_user(user_id):
    user = User.query.get(user_id)
    if user is None:
        return jsonify({"error": "User not found"}), 404
    db.session.delete(user)
    db.session.commit()
    return jsonify({"message": "User deleted successfully"})


@app.route("/admin/stats", methods=["GET"])
def get_stats():
    total_users = User.query.count()
    return jsonify({"total_users": total_users})


@app.route("/users", methods=["POST"])
def create_user():
    data = request.get_json()
    if "username" not in data or "email" not in data or "password" not in data:
        return jsonify({"error": "Missing required fields"}), 400
    user = User.query.filter_by(email=data["email"]).first()
    if user is not None:
        return jsonify({"error": "Email already exists"}), 400
    new_user = User(data["username"], data["email"], data["password"])
    db.session.add(new_user)
    db.session.commit()
    return jsonify(new_user.to_dict()), 201


if __name__ == "__main__":
    app.run(debug=True)
