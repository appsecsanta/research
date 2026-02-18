from flask import Flask, request, make_response
import pdfkit

app = Flask(__name__)

@app.route('/api/export/pdf', methods=['POST'])
def export_pdf():
    data = request.get_json()
    url = data.get('url')
    
    if not url:
        return {'error': 'URL is required'}, 400
    
    try:
        pdf_bytes = pdfkit.from_url(url, False)
        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = 'attachment; filename=export.pdf'
        return response
    except Exception as e:
        return {'error': 'Failed to generate PDF: ' + str(e)}, 500

if __name__ == '__main__':
    app.run(debug=True)
