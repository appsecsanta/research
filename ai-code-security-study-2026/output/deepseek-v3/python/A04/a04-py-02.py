from flask import Flask, request, jsonify
import sqlite3

app = Flask(__name__)

DATABASE = 'shopping_cart.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    return conn

def init_db():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cart (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER,
                quantity INTEGER
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                price REAL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS discount_codes (
                code TEXT PRIMARY KEY,
                discount_percentage REAL
            )
        ''')
        conn.commit()

@app.route('/cart/add', methods=['POST'])
def add_to_cart():
    data = request.json
    product_id = data.get('product_id')
    quantity = data.get('quantity')

    if not product_id or not quantity:
        return jsonify({'error': 'product_id and quantity are required'}), 400

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO cart (product_id, quantity) VALUES (?, ?)', (product_id, quantity))
        conn.commit()

    return jsonify({'message': 'Item added to cart'}), 201

@app.route('/cart', methods=['GET'])
def view_cart():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT products.name, products.price, cart.quantity
            FROM cart
            JOIN products ON cart.product_id = products.id
        ''')
        cart_items = cursor.fetchall()

    cart = [{'name': item[0], 'price': item[1], 'quantity': item[2]} for item in cart_items]
    return jsonify(cart)

@app.route('/cart/checkout', methods=['POST'])
def checkout():
    data = request.json
    discount_code = data.get('discount_code')

    discount_percentage = 0
    if discount_code:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT discount_percentage FROM discount_codes WHERE code = ?', (discount_code,))
            result = cursor.fetchone()
            if result:
                discount_percentage = result[0]

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT products.price, cart.quantity
            FROM cart
            JOIN products ON cart.product_id = products.id
        ''')
        cart_items = cursor.fetchall()

    total = sum(item[0] * item[1] for item in cart_items)
    total -= total * (discount_percentage / 100)

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM cart')
        conn.commit()

    return jsonify({'total': total, 'message': 'Order processed successfully'}), 200

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
