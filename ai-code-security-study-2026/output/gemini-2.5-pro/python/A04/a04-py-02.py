import os
import sqlite3
from flask import Flask, request, session, jsonify, g

# --- App Configuration ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
DATABASE = 'shopping_cart.db'

# --- Database Setup ---

def get_db():
    """Opens a new database connection if there is none yet for the current application context."""
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE, detect_types=sqlite3.PARSE_DECLTYPES)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exception):
    """Closes the database again at the end of the request."""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    """Initializes the database and populates it with sample data."""
    if os.path.exists(DATABASE):
        return

    with app.app_context():
        db = get_db()
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()
        
        # Populate with sample data
        cursor = db.cursor()
        products = [
            ('Laptop', 1200.00),
            ('Mouse', 25.50),
            ('Keyboard', 75.00),
            ('Monitor', 300.99)
        ]
        cursor.executemany('INSERT INTO products (name, price) VALUES (?, ?)', products)

        discounts = [
            ('SAVE10', 10),
            ('DEAL25', 25),
            ('SUMMER50', 50)
        ]
        cursor.executemany('INSERT INTO discount_codes (code, percentage) VALUES (?, ?)', discounts)
        db.commit()
    print("Initialized the database.")

# --- Helper Functions ---

def get_cart_summary(cart_session, discount_code_str=None):
    """
    Calculates the cart summary including subtotal, discount, and total.
    """
    if not cart_session:
        return {
            "items": [],
            "subtotal": 0.0,
            "discount_applied": None,
            "discount_amount": 0.0,
            "total": 0.0
        }

    db = get_db()
    product_ids = list(cart_session.keys())
    
    # Create placeholders for the SQL query
    placeholders = ','.join(['?'] * len(product_ids))
    query = f'SELECT id, name, price FROM products WHERE id IN ({placeholders})'
    
    products = db.execute(query, product_ids).fetchall()
    product_map = {str(p['id']): p for p in products}

    items = []
    subtotal = 0.0

    for product_id, quantity in cart_session.items():
        product_data = product_map.get(product_id)
        if product_data:
            item_total = product_data['price'] * quantity
            subtotal += item_total
            items.append({
                "product_id": product_data['id'],
                "name": product_data['name'],
                "price": product_data['price'],
                "quantity": quantity,
                "item_total": round(item_total, 2)
            })

    discount_percentage = 0
    discount_code_data = None
    if discount_code_str:
        discount_code_data = db.execute(
            'SELECT code, percentage FROM discount_codes WHERE code = ?', (discount_code_str,)
        ).fetchone()
        if discount_code_data:
            discount_percentage = discount_code_data['percentage']

    discount_amount = (subtotal * discount_percentage) / 100
    total = subtotal - discount_amount

    return {
        "items": items,
        "subtotal": round(subtotal, 2),
        "discount_applied": discount_code_data['code'] if discount_code_data else None,
        "discount_amount": round(discount_amount, 2),
        "total": round(total, 2)
    }

# --- API Routes ---

@app.route('/cart/add', methods=['POST'])
def add_to_cart():
    """Adds a product to the cart."""
    data = request.get_json()
    if not data or 'product_id' not in data or 'quantity' not in data:
        return jsonify({"error": "Missing product_id or quantity"}), 400

    try:
        product_id = str(data['product_id'])
        quantity = int(data['quantity'])
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid product_id or quantity format"}), 400

    if quantity <= 0:
        return jsonify({"error": "Quantity must be a positive integer"}), 400

    db = get_db()
    product = db.execute('SELECT id FROM products WHERE id = ?', (product_id,)).fetchone()
    if not product:
        return jsonify({"error": "Product not found"}), 404

    if 'cart' not in session:
        session['cart'] = {}

    # Add or update quantity
    current_quantity = session['cart'].get(product_id, 0)
    session['cart'][product_id] = current_quantity + quantity
    session.modified = True

    return jsonify({
        "message": "Item added to cart successfully",
        "cart": session['cart']
    }), 200

@app.route('/cart', methods=['GET'])
def view_cart():
    """Displays the contents of the cart."""
    cart = session.get('cart', {})
    cart_summary = get_cart_summary(cart)
    return jsonify(cart_summary), 200

@app.route('/cart/checkout', methods=['POST'])
def checkout():
    """Processes the order, applies a discount, and clears the cart."""
    cart = session.get('cart', {})
    if not cart:
        return jsonify({"error": "Cart is empty"}), 400

    data = request.get_json()
    discount_code = data.get('discount_code') if data else None

    db = get_db()
    if discount_code:
        code_exists = db.execute(
            'SELECT id FROM discount_codes WHERE code = ?', (discount_code,)
        ).fetchone()
        if not code_exists:
            return jsonify({"error": "Invalid discount code"}), 400

    order_summary = get_cart_summary(cart, discount_code)
    
    # In a real application, you would now:
    # 1. Create an order in the database.
    # 2. Process payment via a payment gateway.
    # 3. Send a confirmation email.

    # For this example, we just clear the cart.
    session.pop('cart', None)

    return jsonify({
        "message": "Checkout successful",
        "order_summary": order_summary
    }), 200

# --- Main Execution ---

if __name__ == '__main__':
    # Create schema.sql if it doesn't exist
    if not os.path.exists('schema.sql'):
        with open('schema.sql', 'w') as f:
            f.write("""
DROP TABLE IF EXISTS products;
CREATE TABLE products (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  price REAL NOT NULL
);

DROP TABLE IF EXISTS discount_codes;
CREATE TABLE discount_codes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT UNIQUE NOT NULL,
  percentage INTEGER NOT NULL
);
""")
    init_db()
    app.run(debug=True, port=5001)
