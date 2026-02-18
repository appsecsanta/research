import os
import click
from datetime import datetime, timedelta
from flask import (
    Flask,
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    abort,
    request,
)
from flask_sqlalchemy import SQLAlchemy

# --- Configuration ---
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
# It's recommended to store the secret key in an environment variable
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "a_default_secret_key")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'app.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# --- Models ---
class User(db.Model):
    """Represents a user in the database."""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<User {self.username}>"


# --- Admin Blueprint ---
admin_bp = Blueprint(
    "admin", __name__, url_prefix="/admin", template_folder="templates/admin"
)


@admin_bp.route("/")
def index():
    """Redirects to the stats page for a better user experience."""
    return redirect(url_for("admin.stats"))


@admin_bp.route("/users")
def list_users():
    """Lists all users in a paginated view."""
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template("users.html", users=users)


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
def delete_user(user_id):
    """Deletes a user by their ID."""
    user = db.session.get(User, user_id)
    if user is None:
        abort(404)
    
    db.session.delete(user)
    db.session.commit()
    flash(f"User '{user.username}' has been deleted successfully.", "success")
    return redirect(url_for("admin.list_users"))


@admin_bp.route("/stats")
def stats():
    """Displays site statistics."""
    total_users = db.session.query(User.id).count()
    
    twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
    users_last_24h = db.session.query(User.id).filter(
        User.created_at >= twenty_four_hours_ago
    ).count()
    
    most_recent_user = User.query.order_by(User.created_at.desc()).first()
    
    statistics = {
        "total_users": total_users,
        "users_last_24h": users_last_24h,
        "most_recent_user": most_recent_user.username if most_recent_user else "N/A",
    }
    return render_template("stats.html", stats=statistics)


# Register blueprint with the main app
app.register_blueprint(admin_bp)


# --- Main App Routes ---
@app.route("/")
def home():
    """Redirects to the admin dashboard."""
    return redirect(url_for("admin.index"))


# --- CLI Commands ---
@app.cli.command("init-db")
def init_db_command():
    """Initializes the database and seeds it with sample data."""
    instance_path = os.path.join(BASE_DIR, 'instance')
    if not os.path.exists(instance_path):
        os.makedirs(instance_path)

    db.drop_all()
    db.create_all()

    # Seed data
    users_to_add = [
        User(username="admin", email="admin@example.com"),
        User(username="alice", email="alice@example.com", created_at=datetime.utcnow() - timedelta(hours=5)),
        User(username="bob", email="bob@example.com", created_at=datetime.utcnow() - timedelta(days=1)),
        User(username="charlie", email="charlie@example.com", created_at=datetime.utcnow() - timedelta(days=3)),
    ]
    db.session.bulk_save_objects(users_to_add)
    db.session.commit()
    click.echo("Initialized and seeded the database.")


if __name__ == "__main__":
    app.run(debug=True)
