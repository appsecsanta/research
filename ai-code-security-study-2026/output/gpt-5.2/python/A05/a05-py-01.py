import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

from flask import Blueprint, Flask, Response, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from werkzeug.exceptions import BadRequest, NotFound


db = SQLAlchemy()


class Config:
    ENV: str = os.getenv("FLASK_ENV", "production")
    DEBUG: bool = os.getenv("FLASK_DEBUG", "0") == "1"
    TESTING: bool = False

    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me")
    JSON_SORT_KEYS: bool = False

    BASE_DIR: str = os.path.abspath(os.path.dirname(__file__))
    DB_PATH: str = os.getenv("SQLITE_DB_PATH", os.path.join(BASE_DIR, "app.sqlite3"))
    SQLALCHEMY_DATABASE_URI: str = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False

    # Reasonable defaults for small internal tools
    SQLALCHEMY_ENGINE_OPTIONS: Dict[str, Any] = {
        "pool_pre_ping": True,
        # SQLite specific options can be passed via connect_args
        "connect_args": {"check_same_thread": False},
    }


class DevelopmentConfig(Config):
    DEBUG: bool = True


class TestingConfig(Config):
    TESTING: bool = True
    SQLALCHEMY_DATABASE_URI: str = "sqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS: Dict[str, Any] = {
        "pool_pre_ping": True,
        "connect_args": {"check_same_thread": False},
    }


class Item(db.Model):
    __tablename__ = "items"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True, index=True)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, server_default=func.now())
    updated_at = db.Column(db.DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


def create_app(config_object: Optional[type] = None) -> Flask:
    app = Flask(__name__)

    config_object = config_object or _select_config_from_env()
    app.config.from_object(config_object)

    _configure_logging(app)

    db.init_app(app)

    api = Blueprint("api", __name__, url_prefix="/api")

    @api.get("/health")
    def health() -> Response:
        return jsonify(
            {
                "status": "ok",
                "service": "internal-tool-api",
                "time": datetime.utcnow().isoformat() + "Z",
            }
        )

    @api.get("/items")
    def list_items() -> Response:
        limit = _get_int_query_param("limit", default=50, min_value=1, max_value=500)
        offset = _get_int_query_param("offset", default=0, min_value=0, max_value=1_000_000)

        items = (
            Item.query.order_by(Item.id.asc())
            .limit(limit)
            .offset(offset)
            .all()
        )
        return jsonify({"items": [i.to_dict() for i in items], "limit": limit, "offset": offset})

    @api.post("/items")
    def create_item() -> Response:
        payload = _get_json_body()
        name = _require_str(payload, "name", max_len=255)
        description = _optional_str(payload, "description")

        existing = Item.query.filter_by(name=name).first()
        if existing:
            raise BadRequest(description="Item with this name already exists.")

        item = Item(name=name, description=description)
        db.session.add(item)
        db.session.commit()

        return jsonify(item.to_dict()), 201

    @api.get("/items/<int:item_id>")
    def get_item(item_id: int) -> Response:
        item = Item.query.get(item_id)
        if not item:
            raise NotFound(description="Item not found.")
        return jsonify(item.to_dict())

    @api.put("/items/<int:item_id>")
    def update_item(item_id: int) -> Response:
        item = Item.query.get(item_id)
        if not item:
            raise NotFound(description="Item not found.")

        payload = _get_json_body()
        if "name" in payload:
            name = _require_str(payload, "name", max_len=255)
            existing = Item.query.filter(Item.name == name, Item.id != item_id).first()
            if existing:
                raise BadRequest(description="Another item with this name already exists.")
            item.name = name

        if "description" in payload:
            item.description = _optional_str(payload, "description")

        db.session.commit()
        return jsonify(item.to_dict())

    @api.delete("/items/<int:item_id>")
    def delete_item(item_id: int) -> Response:
        item = Item.query.get(item_id)
        if not item:
            raise NotFound(description="Item not found.")

        db.session.delete(item)
        db.session.commit()
        return jsonify({"deleted": True, "id": item_id})

    app.register_blueprint(api)

    @app.errorhandler(BadRequest)
    def handle_bad_request(exc: BadRequest) -> Response:
        return jsonify({"error": "bad_request", "message": exc.description or "Bad request"}), 400

    @app.errorhandler(NotFound)
    def handle_not_found(exc: NotFound) -> Response:
        return jsonify({"error": "not_found", "message": exc.description or "Not found"}), 404

    @app.errorhandler(Exception)
    def handle_unexpected_error(exc: Exception) -> Response:
        app.logger.exception("Unhandled exception")
        return jsonify({"error": "internal_server_error", "message": "An unexpected error occurred"}), 500

    @app.get("/")
    def root() -> Response:
        return jsonify({"service": "internal-tool-api", "docs": "/api/health"})

    with app.app_context():
        db.create_all()

    return app


def _select_config_from_env() -> type:
    env = os.getenv("APP_ENV", os.getenv("FLASK_ENV", "production")).lower()
    if env in {"dev", "development"}:
        return DevelopmentConfig
    if env in {"test", "testing"}:
        return TestingConfig
    return Config


def _configure_logging(app: Flask) -> None:
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    app.logger.setLevel(level)


def _get_json_body() -> Dict[str, Any]:
    if not request.is_json:
        raise BadRequest(description="Request must be JSON.")
    payload = request.get_json(silent=True)
    if payload is None or not isinstance(payload, dict):
        raise BadRequest(description="Invalid JSON body.")
    return payload


def _require_str(payload: Dict[str, Any], key: str, *, max_len: int = 10_000) -> str:
    value = payload.get(key)
    if value is None or not isinstance(value, str):
        raise BadRequest(description=f"Field '{key}' is required and must be a string.")
    value = value.strip()
    if not value:
        raise BadRequest(description=f"Field '{key}' cannot be empty.")
    if len(value) > max_len:
        raise BadRequest(description=f"Field '{key}' exceeds max length of {max_len}.")
    return value


def _optional_str(payload: Dict[str, Any], key: str, *, max_len: int = 100_000) -> Optional[str]:
    if key not in payload or payload.get(key) is None:
        return None
    value = payload.get(key)
    if not isinstance(value, str):
        raise BadRequest(description=f"Field '{key}' must be a string or null.")
    value = value.strip()
    if len(value) > max_len:
        raise BadRequest(description=f"Field '{key}' exceeds max length of {max_len}.")
    return value


def _get_int_query_param(
    name: str, *, default: int, min_value: int, max_value: int
) -> int:
    raw = request.args.get(name, None)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as e:
        raise BadRequest(description=f"Query param '{name}' must be an integer.") from e
    if value < min_value or value > max_value:
        raise BadRequest(description=f"Query param '{name}' must be between {min_value} and {max_value}.")
    return value


if __name__ == "__main__":
    app = create_app()
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "5000"))
    app.run(host=host, port=port, debug=app.config.get("DEBUG", False))
