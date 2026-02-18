import base64
import binascii
import json
import os
from datetime import datetime, timezone
from typing import Any

from flask import Flask, jsonify, request
from sqlalchemy import DateTime, Integer, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, scoped_session, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///import.db")


class Base(DeclarativeBase):
    pass


class ImportedObject(Base):
    __tablename__ = "imported_objects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    data_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


engine = create_engine(
    DATABASE_URL,
    future=True,
    echo=False,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)

Base.metadata.create_all(engine)

SessionFactory = scoped_session(
    sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)
)

app = Flask(__name__)
app.config.setdefault("MAX_CONTENT_LENGTH", 25 * 1024 * 1024)  # 25MB


def _extract_base64_payload() -> str:
    if request.is_json:
        body = request.get_json(silent=True) or {}
        payload = body.get("payload")
        if isinstance(payload, str) and payload.strip():
            return payload.strip()
    raw = request.get_data(cache=False, as_text=True) or ""
    raw = raw.strip()
    if not raw:
        raise ValueError("Empty request body")
    return raw


def _decode_and_deserialize(payload_b64: str) -> Any:
    try:
        decoded = base64.b64decode(payload_b64, validate=True)
    except (binascii.Error, ValueError) as e:
        raise ValueError("Invalid base64 payload") from e

    try:
        return json.loads(decoded.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ValueError("Decoded payload is not valid UTF-8 JSON") from e


@app.post("/api/import")
def api_import():
    session: Session = SessionFactory()
    try:
        payload_b64 = _extract_base64_payload()
        data = _decode_and_deserialize(payload_b64)

        objects: list[Any]
        if isinstance(data, list):
            objects = data
        elif isinstance(data, dict):
            objects = [data]
        else:
            return jsonify({"error": "JSON payload must be an object or an array of objects"}), 400

        rows = [ImportedObject(data_json=json.dumps(obj, separators=(",", ":"), ensure_ascii=False)) for obj in objects]
        session.add_all(rows)
        session.commit()

        return jsonify({"imported": len(rows)}), 201
    except ValueError as e:
        session.rollback()
        return jsonify({"error": str(e)}), 400
    except Exception:
        session.rollback()
        return jsonify({"error": "Internal server error"}), 500
    finally:
        session.close()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
