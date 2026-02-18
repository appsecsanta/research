# main.py
# To run this:
# 1. Install dependencies: pip install Flask Flask-Cors
# 2. Run the server: python main.py

from flask import Flask, jsonify
from flask_cors import CORS

# --- App Initialization ---
app = Flask(__name__)


# --- CORS Configuration ---
# This will allow the React frontend at http://localhost:3000 to make requests
# to this Flask API.
# The `origins` parameter can be a string, a list of strings, or a regex.
# For production, you would replace 'http://localhost:3000' with your
# actual frontend domain, e.g., 'https://your-react-app.com'.
CORS(
    app,
    origins=["http://localhost:3000"],
    supports_credentials=True  # This is important for sessions, cookies, etc.
)


# --- API Endpoints ---
@app.route("/api/status", methods=["GET"])
def get_status():
    """
    A simple endpoint to check if the API is running and CORS is working.
    """
    return jsonify({"status": "ok", "message": "API is running!"})


@app.route("/api/data", methods=["GET"])
def get_data():
    """
    An example endpoint that returns some data.
    """
    sample_data = {
        "id": 1,
        "name": "Sample Item",
        "description": "This data came from the Flask backend.",
        "tags": ["python", "flask", "react", "cors"]
    }
    return jsonify(sample_data)


# --- Main Execution ---
if __name__ == "__main__":
    # Note: In a production environment, use a proper WSGI server
    # like Gunicorn or uWSGI instead of the built-in development server.
    # Example with Gunicorn: gunicorn --bind 0.0.0.0:5001 main:app
    app.run(host="0.0.0.0", port=5001, debug=True)
