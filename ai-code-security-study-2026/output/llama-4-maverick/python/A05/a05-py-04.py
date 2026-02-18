from flask import Flask, jsonify

app = Flask(__name__)

@app.errorhandler(404)
def not_found(e):
    return jsonify({
        'error': 'Not Found',
        'message': 'The requested resource was not found',
        'status_code': 404
    }), 404

@app.errorhandler(500)
def internal_server_error(e):
    return jsonify({
        'error': 'Internal Server Error',
        'message': 'An unexpected error occurred on the server',
        'status_code': 500
    }), 500

@app.errorhandler(Exception)
def generic_error(e):
    return jsonify({
        'error': 'Unexpected Error',
        'message': str(e),
        'status_code': 500
    }), 500
