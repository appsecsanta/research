from flask import Flask, request, jsonify
import subprocess
import re

app = Flask(__name__)

def is_valid_host(host):
    # Simple validation for hostname or IP
    hostname_regex = re.compile(r'^([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])(\.([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\-]{0,61}[a-zA-Z0-9]))*$')
    ipv4_regex = re.compile(r'^(\d{1,3}\.){3}\d{1,3}$')
    ipv6_regex = re.compile(r'^(([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,7}:|([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,5}(:[0-9a-fA-F]{1,4}){1,2}|([0-9a-fA-F]{1,4}:){1,4}(:[0-9a-fA-F]{1,4}){1,3}|([0-9a-fA-F]{1,4}:){1,3}(:[0-9a-fA-F]{1,4}){1,4}|([0-9a-fA-F]{1,4}:){1,2}(:[0-9a-fA-F]{1,4}){1,5}|[0-9a-fA-F]{1,4}:((:[0-9a-fA-F]{1,4}){1,6})|:((:[0-9a-fA-F]{1,4}){1,7}|:)|fe80:(:[0-9a-fA-F]{0,4}){0,4}%[0-9a-zA-Z]{1,}|::(ffff(:0{1,4}){0,1}:){0,1}((\d{1,3}\.){3}\d{1,3})|([0-9a-fA-F]{1,4}:){1,4}:(\d{1,3}\.){3}\d{1,3})$')
    return bool(hostname_regex.match(host) or ipv4_regex.match(host) or ipv6_regex.match(host))

@app.route('/api/tools/ping', methods=['POST'])
def ping_host():
    data = request.get_json()
    if not data or 'host' not in data:
        return jsonify({'error': 'Missing "host" field in JSON body'}), 400
    
    host = data['host']
    if not isinstance(host, str) or not is_valid_host(host):
        return jsonify({'error': 'Invalid host provided'}), 400
    
    try:
        # Run ping with 4 packets, capture output
        result = subprocess.run(['ping', '-c', '4', host], capture_output=True, text=True, timeout=10)
        output = result.stdout if result.returncode == 0 else result.stderr
        return jsonify({'output': output}), 200 if result.returncode == 0 else 500
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Ping timed out'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
