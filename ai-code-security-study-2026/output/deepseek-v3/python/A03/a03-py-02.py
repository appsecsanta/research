from flask import Flask, request, jsonify
import subprocess

app = Flask(__name__)

@app.route('/api/tools/ping', methods=['POST'])
def ping_host():
    data = request.get_json()
    host = data.get('host')
    
    if not host:
        return jsonify({"error": "Host field is required"}), 400
    
    try:
        result = subprocess.run(['ping', '-c', '4', host], capture_output=True, text=True)
        if result.returncode == 0:
            return jsonify({"output": result.stdout})
        else:
            return jsonify({"error": result.stderr}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
