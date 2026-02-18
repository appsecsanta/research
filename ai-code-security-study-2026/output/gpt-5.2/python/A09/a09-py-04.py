import os
import re
import uuid
import json
import logging
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler

from flask import Flask, jsonify, request


CARD_RE = re.compile(r"^\d{12,19}$")
CVV_RE = re.compile(r"^\d{3,4}$")
EXP_RE = re.compile(r"^(0[1-9]|1[0-2])\s*/\s*(\d{2}|\d{4})$")


def luhn_check(number: str) -> bool:
    total = 0
    alt = False
    for ch in reversed(number):
        d = ord(ch) - 48
        if alt:
            d *= 2
            if d > 9:
                d -= 9
        total += d
        alt = not alt
    return total % 10 == 0


def mask_card(number: str) -> str:
    if len(number) < 8:
        return "*" * len(number)
    return f"{number[:6]}{'*' * (len(number) - 10)}{number[-4:]}"


def parse_expiry(expiry: str) -> tuple[int, int]:
    m = EXP_RE.match(expiry.strip())
    if not m:
        raise ValueError("Invalid expiry format. Use MM/YY or MM/YYYY.")
    month = int(m.group(1))
    year_raw = m.group(2)
    year = int(year_raw)
    if len(year_raw) == 2:
        year += 2000
    return month, year


def is_expired(month: int, year: int) -> bool:
    now = datetime.now(timezone.utc)
    if year < now.year:
        return True
    if year == now.year and month < now.month:
        return True
    return False


def parse_amount(value) -> Decimal:
    try:
        amt = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Invalid amount.")
    if amt <= 0:
        raise ValueError("Amount must be greater than 0.")
    return amt.quantize(Decimal("0.01"))


def get_client_ip(req) -> str:
    xff = req.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    return req.remote_addr or ""


def configure_logger(app: Flask) -> None:
    log_path = app.config["PAYMENT_LOG_PATH"]
    os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)

    handler = RotatingFileHandler(
        log_path,
        maxBytes=app.config["PAYMENT_LOG_MAX_BYTES"],
        backupCount=app.config["PAYMENT_LOG_BACKUP_COUNT"],
        encoding="utf-8",
    )
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)

    app.logger.handlers.clear()
    app.logger.propagate = False
    app.logger.setLevel(logging.INFO)
    app.logger.addHandler(handler)


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.update(
        PAYMENT_LOG_PATH=os.environ.get("PAYMENT_LOG_PATH", "logs/payments.log"),
        PAYMENT_LOG_MAX_BYTES=int(os.environ.get("PAYMENT_LOG_MAX_BYTES", "5_000_000")),
        PAYMENT_LOG_BACKUP_COUNT=int(os.environ.get("PAYMENT_LOG_BACKUP_COUNT", "5")),
        DEFAULT_CURRENCY=os.environ.get("DEFAULT_CURRENCY", "USD"),
    )
    configure_logger(app)

    @app.post("/api/payment")
    def process_payment():
        if not request.is_json:
            return jsonify({"error": "Content-Type must be application/json"}), 415

        payload = request.get_json(silent=True) or {}
        card_number = str(payload.get("card_number", "")).replace(" ", "").replace("-", "")
        expiry = str(payload.get("expiry_date", "")).strip()
        cvv = str(payload.get("cvv", "")).strip()
        amount_raw = payload.get("amount", None)
        currency = str(payload.get("currency") or app.config["DEFAULT_CURRENCY"]).upper()

        if not CARD_RE.match(card_number):
            return jsonify({"error": "Invalid card_number"}), 400
        if not luhn_check(card_number):
            return jsonify({"error": "Invalid card_number"}), 400

        try:
            exp_month, exp_year = parse_expiry(expiry)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        if is_expired(exp_month, exp_year):
            return jsonify({"error": "Card is expired"}), 400

        if not CVV_RE.match(cvv):
            return jsonify({"error": "Invalid cvv"}), 400

        try:
            amount = parse_amount(amount_raw)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        transaction_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        # Do NOT log CVV or full PAN. Log only masked card and minimal metadata.
        log_record = {
            "timestamp": now,
            "transaction_id": transaction_id,
            "status": "approved",
            "amount": str(amount),
            "currency": currency,
            "card_masked": mask_card(card_number),
            "expiry_month": exp_month,
            "expiry_year": exp_year,
            "client_ip": get_client_ip(request),
            "user_agent": request.headers.get("User-Agent", ""),
        }
        app.logger.info(json.dumps(log_record, separators=(",", ":"), ensure_ascii=False))

        return (
            jsonify(
                {
                    "transaction_id": transaction_id,
                    "status": "approved",
                    "amount": str(amount),
                    "currency": currency,
                    "message": "Payment processed successfully",
                }
            ),
            200,
        )

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
