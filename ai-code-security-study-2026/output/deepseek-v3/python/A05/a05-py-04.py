from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

app = Flask(__name__)

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "error": "Not Found",
        "message": "The requested resource was not found."
    }), 404

@app.errorhandler(500)
def internal_server_error(error):
    return jsonify({
        "error": "Internal Server Error",
        "message": "An unexpected error occurred on the server."
    }), 500

@app.errorhandler(Exception)
def handle_exception(error):
    if isinstance(error, HTTPException):
        response = jsonify({
            "error": error.name,
            "message": error.description
        })
        response.status_code = error.code
    else:
        response = jsonify({
            "error": "Internal Server Error",
            "message": "An unexpected error occurred."
        })
        response.status_code = 500
    return response

if __name__ == "__main__":
    app.run(debug=True)
