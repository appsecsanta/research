import requests
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/api/preview', methods=['POST'])
def preview():
    data = request.json
    url = data.get('url')
    if not url:
        return jsonify({'error': 'URL is required'}), 400
    
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
    except requests.RequestException as e:
        return jsonify({'error': str(e)}), 500
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    title = soup.title.string.strip() if soup.title else None
    
    meta_desc = soup.find('meta', attrs={'name': 'description'})
    description = meta_desc['content'].strip() if meta_desc and 'content' in meta_desc.attrs else None
    
    return jsonify({'title': title, 'description': description})
