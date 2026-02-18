import sqlite3
import threading
import time
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

DATABASE = "webhooks.db"


def get_db():
    """Get a database connection for the current context."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize the database schema."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS webhooks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL UNIQUE,
            secret TEXT,
            events TEXT NOT NULL DEFAULT '*',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS webhook_deliveries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            webhook_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            payload TEXT NOT NULL,
            response_status INTEGER,
            response_body TEXT,
            success INTEGER NOT NULL DEFAULT 0,
            attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (webhook_id) REFERENCES webhooks(id)
        )
    """)
    conn.commit()
    conn.close()


@app.route("/api/webhooks/register", methods=["POST"])
def register_webhook():
    """Register a new webhook URL."""
    data = request.get_json()

    if not data or "url" not in data:
        return jsonify({"error": "Missing required field: url"}), 400

    url = data["url"].strip()
    if not url.startswith(("http://", "https://")):
        return jsonify({"error": "Invalid URL. Must start with http:// or https://"}), 400

    secret = data.get("secret")
    events = data.get("events", "*")

    if isinstance(events, list):
        events = ",".join(events)

    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO webhooks (url, secret, events) VALUES (?, ?, ?)",
            (url, secret, events),
        )
        conn.commit()
        webhook_id = cursor.lastrowid

        return jsonify({
            "message": "Webhook registered successfully",
            "webhook": {
                "id": webhook_id,
                "url": url,
                "events": events,
                "is_active": True,
            },
        }), 201

    except sqlite3.IntegrityError:
        return jsonify({"error": "Webhook URL already registered"}), 409
    finally:
        conn.close()


@app.route("/api/webhooks", methods=["GET"])
def list_webhooks():
    """List all registered webhooks."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, url, events, is_active, created_at FROM webhooks")
    rows = cursor.fetchall()
    conn.close()

    webhooks = [
        {
            "id": row["id"],
            "url": row["url"],
            "events": row["events"],
            "is_active": bool(row["is_active"]),
            "created_at": row["created_at"],
        }
        for row in rows
    ]

    return jsonify({"webhooks": webhooks}), 200


@app.route("/api/webhooks/<int:webhook_id>", methods=["DELETE"])
def delete_webhook(webhook_id):
    """Delete a registered webhook."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM webhooks WHERE id = ?", (webhook_id,))
    conn.commit()
    affected = cursor.rowcount
    conn.close()

    if affected == 0:
        return jsonify({"error": "Webhook not found"}), 404

    return jsonify({"message": "Webhook deleted successfully"}), 200


@app.route("/api/webhooks/<int:webhook_id>/toggle", methods=["PATCH"])
def toggle_webhook(webhook_id):
    """Activate or deactivate a webhook."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE webhooks SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END WHERE id = ?",
        (webhook_id,),
    )
    conn.commit()

    if cursor.rowcount == 0:
        conn.close()
        return jsonify({"error": "Webhook not found"}), 404

    cursor.execute("SELECT is_active FROM webhooks WHERE id = ?", (webhook_id,))
    row = cursor.fetchone()
    conn.close()

    return jsonify({
        "message": "Webhook updated",
        "is_active": bool(row["is_active"]),
    }), 200


def get_active_webhooks_for_event(event_type):
    """Retrieve all active webhooks that are subscribed to a given event type."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, url, secret, events FROM webhooks WHERE is_active = 1")
    rows = cursor.fetchall()
    conn.close()

    matching = []
    for row in rows:
        subscribed_events = row["events"].split(",")
        if "*" in subscribed_events or event_type in subscribed_events:
            matching.append({
                "id": row["id"],
                "url": row["url"],
                "secret": row["secret"],
                "events": row["events"],
            })

    return matching


def log_delivery(webhook_id, event_type, payload, response_status, response_body, success):
    """Log a webhook delivery attempt."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO webhook_deliveries
           (webhook_id, event_type, payload, response_status, response_body, success)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (webhook_id, event_type, str(payload), response_status, response_body, int(success)),
    )
    conn.commit()
    conn.close()


def send_webhook(webhook, event_type, event_data, max_retries=3, retry_delay=2):
    """Send event data to a single webhook URL with retry logic."""
    payload = {
        "event_type": event_type,
        "timestamp": time.time(),
        "data": event_data,
    }

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "WebhookService/1.0",
        "X-Event-Type": event_type,
    }

    if webhook.get("secret"):
        import hashlib
        import hmac
        import json

        signature = hmac.new(
            webhook["secret"].encode("utf-8"),
            json.dumps(payload, sort_keys=True).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        headers["X-Webhook-Signature"] = signature

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(
                webhook["url"],
                json=payload,
                headers=headers,
                timeout=10,
            )

            success = 200 <= response.status_code < 300
            log_delivery(
                webhook_id=webhook["id"],
                event_type=event_type,
                payload=payload,
                response_status=response.status_code,
                response_body=response.text[:1000],
                success=success,
            )

            if success:
                return True

            if attempt < max_retries:
                time.sleep(retry_delay * attempt)

        except requests.RequestException as e:
            log_delivery(
                webhook_id=webhook["id"],
                event_type=event_type,
                payload=payload,
                response_status=None,
                response_body=str(e)[:1000],
                success=False,
            )

            if attempt < max_retries:
                time.sleep(retry_delay * attempt)

    return False


def dispatch_event(event_type, event_data):
    """
    Dispatch an event to all registered and active webhooks.
    Sends POST requests asynchronously using threads.
    """
    webhooks = get_active_webhooks_for_event(event_type)

    if not webhooks:
        return {"event_type": event_type, "webhooks_notified": 0}

    threads = []
    results = {}

    def _send(wh):
        results[wh["id"]] = send_webhook(wh, event_type, event_data)

    for webhook in webhooks:
        t = threading.Thread(target=_send, args=(webhook,))
        t.start()
        threads.append(t)

    for t in threads:
        t.join(timeout=35)

    return {
        "event_type": event_type,
        "webhooks_notified": len(webhooks),
        "results": {wh_id: "success" if ok else "failed" for wh_id, ok in results.items()},
    }


# Convenience endpoint to manually trigger an event (useful for testing)
@app.route("/api/events/trigger", methods=["POST"])
def trigger_event():
    """Trigger an event manually (for testing purposes)."""
    data = request.get_json()

    if not data or "event_type" not in data:
        return jsonify({"error": "Missing required field: event_type"}), 400

    event_type = data["event_type"]
    event_data = data.get("data", {})

    result = dispatch_event(event_type, event_data)

    return jsonify({
        "message": "Event dispatched",
        "result": result,
    }), 200


@app.route("/api/webhooks/<int:webhook_id>/deliveries", methods=["GET"])
def get_deliveries(webhook_id):
    """Get delivery history for a specific webhook."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT id, event_type, payload, response_status, response_body, success, attempted_at
           FROM webhook_deliveries
           WHERE webhook_id = ?
           ORDER BY attempted_at DESC
           LIMIT 50""",
        (webhook_id,),
    )
    rows = cursor.fetchall()
    conn.close()

    deliveries = [
        {
            "id": row["id"],
            "event_type": row["event_type"],
            "response_status": row["response_status"],
            "success": bool(row["success"]),
            "attempted_at": row["attempted_at"],
        }
        for row in rows
    ]

    return jsonify({"deliveries": deliveries}), 200


# Initialize database on startup
init_db()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
