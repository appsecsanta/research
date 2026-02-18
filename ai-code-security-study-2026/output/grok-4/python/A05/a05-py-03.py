from flask import Flask
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "http://localhost:3000"}})

# Example route for testing
@app.route('/api/example', methods=['GET'])
def example():
    return {"message": "CORS-enabled response"}

if __name__ == '__main__':
    app.run(debug=True)
