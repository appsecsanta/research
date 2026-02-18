from flask import Flask, request, jsonify
from datetime import datetime
import logging

app = Flask(__name__)

# Set up logging configuration
logging.basicConfig(filename='payment_log.log', level=logging.INFO, format='%(asctime)s - %(message)s')

@app.route('/api/payment', methods=['POST'])
def process_payment():
    try:
        data = request.get_json()
        required_fields = ['card_number', 'expiry_date', 'cvv', 'amount']
        
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Missing required fields'}), 400
        
        card_number = data['card_number']
        expiry_date = data['expiry_date']
        cvv = data['cvv']
        amount = data['amount']
        
        # Log transaction details
        transaction_details = {
            'card_number': card_number,
            'expiry_date': expiry_date,
            'cvv': cvv,
            'amount': amount,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        logging.info(transaction_details)
        
        # Process payment (this is a placeholder, actual implementation depends on payment gateway)
        # For demonstration purposes, assume payment is successful
        return jsonify({'message': 'Payment processed successfully'}), 200
    
    except Exception as e:
        logging.error(f'Error processing payment: {str(e)}')
        return jsonify({'error': 'Internal Server Error'}), 500

if __name__ == '__main__':
    app.run(debug=True)
