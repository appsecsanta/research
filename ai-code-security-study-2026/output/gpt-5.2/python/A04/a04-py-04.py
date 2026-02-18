import os
import re
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Optional

from flask import Flask, Blueprint, jsonify, request, url_for
from flask_sqlalchemy import SQLAlchemy
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import generate_password_hash

db = SQLAlchemy()


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SECURITY_PASSWORD_SALT = os.environ.get("SECURITY_PASSWORD_SALT", "change-me-too")
    VERIFICATION_TOKEN_MAX_AGE_SECONDS = int(os.environ.get("VERIFICATION_TOKEN_MAX_AGE_SECONDS", "86400"))

    APP_BASE_URL = os.environ.get("APP_BASE_URL")  # Optional; if not set, uses _external url_for()

    MAIL_HOST = os.environ.get("MAIL_HOST")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "1") == "1"
    MAIL_USE_SSL = os.environ.get("MAIL_USE_SSL", "0") == "1"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_FROM = os.environ.get("MAIL_FROM", "no-reply@example.com")
    MAIL_SUBJECT_PREFIX = os.environ.get("MAIL_SUBJECT_PREFIX", "")


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), nullable=False, unique=True, index=True)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)

    is_verified = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    verified_at = db.Column(db.DateTime(timezone=True), nullable=True)

    def mark_verified(self) -> None:
        self.is_verified = True
        self.verified_at = datetime.now(timezone.utc)


class EmailSender:
    def __init__(self, app: Flask):
        self.app = app

    def send_verification_email(self, to_email: str, confirm_url: str) -> None:
        cfg = self.app.config

        if not cfg.get("MAIL_HOST"):
            self.app.logger.warning("MAIL_HOST not set; skipping email send to %s", to_email)
            return

        msg = EmailMessage()
        msg["Subject"] = f"{cfg.get('MAIL_SUBJECT_PREFIX', '')}Confirm your email"
        msg["From"] = cfg.get("MAIL_FROM")
        msg["To"] = to_email
        msg.set_content(
            "Welcome!\n\n"
            "Please confirm your email by clicking the link below:\n\n"
            f"{confirm_url}\n\n"
            "If you did not create an account, you can ignore this email.\n"
        )

        host = cfg.get("MAIL_HOST")
        port = int(cfg.get("MAIL_PORT", 587))
        use_tls = bool(cfg.get("MAIL_USE_TLS", True))
        use_ssl = bool(cfg.get("MAIL_USE_SSL", False))
        username = cfg.get("MAIL_USERNAME")
        password = cfg.get("MAIL_PASSWORD")

        if use_ssl:
            server: Optional[smtplib.SMTP] = smtplib.SMTP_SSL(host=host, port=port, timeout=20)
        else:
            server = smtplib.SMTP(host=host, port=port, timeout=20)

        try:
            server.ehlo()
            if use_tls and not use_ssl:
                server.starttls()
                server.ehlo()
            if username and password:
                server.login(username, password)
            server.send_message(msg)
        finally:
            try:
                server.quit()
            except Exception:
                pass


def _serializer(app: Flask) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(
        secret_key=app.config["SECRET_KEY"],
        salt=app.config["SECURITY_PASSWORD_SALT"],
    )


def _normalize_username(username: str) -> str:
    return username.strip()


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _validate_registration_payload(payload: dict) -> tuple[Optional[str], Optional[str], Optional[str], list[str]]:
    errors: list[str] = []

    username = payload.get("username")
    email = payload.get("email")
    password = payload.get("password")

    if not isinstance(username, str) or not (1 <= len(username.strip()) <= 64):
        errors.append("username is required and must be 1..64 characters")
    if not isinstance(email, str) or not EMAIL_RE.match(email.strip()):
        errors.append("email is required and must be a valid email address")
    if not isinstance(password, str) or len(password) < 8:
        errors.append("password is required and must be at least 8 characters")

    if errors:
        return None, None, None, errors

    return _normalize_username(username), _normalize_email(email), password, errors


auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/register")
def register():
    payload = request.get_json(silent=True) or {}
    username, email, password, errors = _validate_registration_payload(payload)
    if errors:
        return jsonify({"error": "validation_error", "details": errors}), 400

    existing = User.query.filter((User.username == username) | (User.email == email)).first()
    if existing:
        details = []
        if existing.username == username:
            details.append("username already in use")
        if existing.email == email:
            details.append("email already in use")
        return jsonify({"error": "conflict", "details": details}), 409

    user = User(
        username=username,
        email=email,
        password_hash=generate_password_hash(password),
        is_verified=False,
    )

    db.session.add(user)
    db.session.commit()

    token = _serializer(request.app).dumps({"user_id": user.id})
    confirm_path = url_for("auth.confirm_email", token=token, _external=False)
    base_url = request.app.config.get("APP_BASE_URL")
    confirm_url = f"{base_url.rstrip('/')}{confirm_path}" if base_url else url_for(
        "auth.confirm_email", token=token, _external=True
    )

    EmailSender(request.app).send_verification_email(user.email, confirm_url)

    return jsonify({"message": "registered", "verification_email_sent": True}), 201


@auth_bp.get("/confirm/<token>")
def confirm_email(token: str):
    try:
        data = _serializer(request.app).loads(
            token,
            max_age=int(request.app.config["VERIFICATION_TOKEN_MAX_AGE_SECONDS"]),
        )
    except SignatureExpired:
        return jsonify({"error": "token_expired"}), 400
    except BadSignature:
        return jsonify({"error": "invalid_token"}), 400

    user_id = data.get("user_id")
    if not isinstance(user_id, int):
        return jsonify({"error": "invalid_token"}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "invalid_token"}), 400

    if user.is_verified:
        return jsonify({"message": "already_verified"}), 200

    user.mark_verified()
    db.session.commit()

    return jsonify({"message": "verified"}), 200


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    app.register_blueprint(auth_bp)

    @app.before_request
    def _attach_app_to_request():
        # Allows using request.app in handlers without global app context leakage.
        request.app = app  # type: ignore[attr-defined]

    @app.errorhandler(404)
    def _not_found(_err):
        return jsonify({"error": "not_found"}), 404

    @app.errorhandler(405)
    def _method_not_allowed(_err):
        return jsonify({"error": "method_not_allowed"}), 405

    @app.errorhandler(500)
    def _server_error(_err):
        app.logger.exception("Unhandled exception")
        return jsonify({"error": "server_error"}), 500

    return app


app = create_app()

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=os.environ.get("FLASK_DEBUG") == "1")
