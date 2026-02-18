from flask import Flask, request, send_file
import requests
from io import BytesIO
from urllib.parse import urlparse

app = Flask(__name__)

@app.route('/api/image-proxy', methods=['GET'])
def image_proxy():
    url = request.args.get('url')
    if not url:
        return 'Missing required "url" parameter', 400
    
    try:
        result = urlparse(url)
        if not all([result.scheme, result.netloc]):
            return 'Invalid URL', 400
    except ValueError:
        return 'Invalid URL', 400

    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
    except requests.RequestException as e:
        return f'Failed to fetch image: {e}', 502

    image_data = BytesIO()
    for chunk in response.iter_content(1024):
        image_data.write(chunk)
    image_data.seek(0)

    return send_file(
        image_data,
        mimetype=response.headers.get('Content-Type', 'application/octet-stream')
    )

if __name__ == '__main__':
    app.run(debug=True)
