# In a separate file named 'requirements.txt':
# Flask==3.0.3

# In a separate file named '.gitignore':
# __pycache__/
# *.pyc
# venv/
# instance/
# .env
# .flaskenv
# logs/

import logging
import os
import uuid
from datetime import datetime
from logging.handlers import RotatingFileHandler

from flask import Flask, jsonify, request

# --- Application Setup ---
app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False


# --- Logging Configuration ---
def setup_logging(app_instance):
    """Configures file-based, rotating logging for the application."""
    if not os.path.exists("logs"):
        os.makedirs("logs")

    # Use RotatingFileHandler to prevent log files from growing indefinitely
    log_handler = RotatingFileHandler(
        "logs/transactions.log", maxBytes=10240, backupCount=10
    )
    log_formatter = logging.Formatter(
        "%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]"
    )
    log_handler.setFormatter(log_formatter)
    log_handler.setLevel(logging.INFO)

    if not app_instance.debug:
        app_instance.logger.addHandler(log_handler)
        app_instance.logger.setLevel(logging.INFO)
        app_instance.logger.info("Payment API startup")


# --- Helper Functions ---
def validate_payment_data(data):
    """
    Validates the incoming payment request data.
    Returns a tuple (is_valid, error_message).
    """
    if not isinstance(data, dict):
        return False, "Invalid JSON payload."

    required_fields = ["card_number", "expiry_date", "cvv", "amount"]
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return False, f"Missing required fields: {', '.join(missing_fields)}"

    card_number = data.get("card_number")
    expiry_date = data.get("expiry_date")
    cvv = data.get("cvv")
    amount = data.get("amount")

    if (
        not isinstance(card_number, str)
        or not card_number.isdigit()
        or not 13 <= len(card_number) <= 16
    ):
        return False, "Invalid 'card_number'. Must be a string of 13-16 digits."

    if not isinstance(expiry_date, str) or len(expiry_date) != 5 or expiry_date[2] != "/":
        return False, "Invalid 'expiry_date' format. Expected MM/YY."
    try:
        month, year_short = map(int, expiry_date.split("/"))
        current_year_short = int(str(datetime.now().year)[-2:])
        current_month = datetime.now().month
        if not (
            1 <= month <= 12
            and (
                year_short > current_year_short
                or (year_short == current_year_short and month >= current_month)
            )
        ):
            return False, "Expiry date is invalid or in the past."
    except (ValueError, IndexError):
        return False, "Invalid 'expiry_date' values. Expected MM/YY."

    if not isinstance(cvv, str) or not cvv.isdigit() or not 3 <= len(cvv) <= 4:
        return False, "Invalid 'cvv'. Must be a string of 3 or 4 digits."

    if not isinstance(amount, (int, float)) or amount <= 0:
        return False, "Invalid 'amount'. Must be a positive number."

    return True, None


# --- API Endpoints ---
@app.route("/api/payment", methods=["POST"])
def process_payment():
    """
    Processes a payment transaction.
    Expects a JSON payload with card_number, expiry_date, cvv, and amount.
    """
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 415

    data = request.get_json()
    is_valid, error_message = validate_payment_data(data)

    if not is_valid:
        app.logger.warning(f"Invalid payment request: {error_message} - Data: {data}")
        return jsonify({"status": "error", "message": error_message}), 400

    # --- Simulate Payment Gateway Interaction ---
    # In a real application, this is where you would call a payment
    # gateway API (e.g., Stripe, Braintree). For this example, we'll
    # assume the payment is always successful if the data is valid.
    transaction_id = str(uuid.uuid4())
    amount = data["amount"]
    card_last_four = data["card_number"][-4:]

    # --- Secure Logging ---
    # CRITICAL: Never log the full card number, expiry date, or CVV.
    log_message = (
        f"Payment processed: transaction_id={transaction_id}, "
        f"amount={amount:.2f}, card_last4={card_last_four}"
    )
    app.logger.info(log_message)

    # --- Response ---
    response_data = {
        "status": "success",
        "message": "Payment processed successfully.",
        "transaction_id": transaction_id,
        "amount_processed": amount,
    }
    return jsonify(response_data), 200


# --- Error Handlers ---
@app.errorhandler(404)
def not_found_error(error):
    return jsonify({"status": "error", "message": "Resource not found"}), 404


@app.errorhandler(500)
def internal_error(error):
    app.logger.error(f"Server Error: {error}", exc_info=True)
    return jsonify({"status": "error", "message": "An internal server error occurred"}), 500


# --- Main Execution ---
if __name__ == "__main__":
    setup_logging(app)
    # For production, use a proper WSGI server like Gunicorn or uWSGI.
    # Example: gunicorn --bind 0.0.0.0:5000 app:app
    app.run(host="0.0.0.0", port=5000, debug=False)
