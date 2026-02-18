from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///shopping_cart.db"
db = SQLAlchemy(app)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)

    def __repr__(self):
        return f"Product('{self.name}', '{self.price}')"


class DiscountCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(100), nullable=False, unique=True)
    discount_percentage = db.Column(db.Float, nullable=False)

    def __repr__(self):
        return f"DiscountCode('{self.code}', '{self.discount_percentage}')"


class Cart:
    def __init__(self):
        self.items = {}

    def add_item(self, product_id, quantity):
        if product_id in self.items:
            self.items[product_id] += quantity
        else:
            self.items[product_id] = quantity

    def view_cart(self):
        cart_items = []
        total = 0
        for product_id, quantity in self.items.items():
            product = Product.query.get(product_id)
            if product:
                item_total = product.price * quantity
                total += item_total
                cart_items.append({
                    "product_id": product_id,
                    "name": product.name,
                    "price": product.price,
                    "quantity": quantity,
                    "total": item_total
                })
        return {"cart_items": cart_items, "total": total}

    def checkout(self, discount_code=None):
        total = 0
        for product_id, quantity in self.items.items():
            product = Product.query.get(product_id)
            if product:
                total += product.price * quantity
        if discount_code:
            discount = DiscountCode.query.filter_by(code=discount_code).first()
            if discount:
                total *= (1 - discount.discount_percentage / 100)
        return {"total": total}


cart = Cart()


@app.route("/cart/add", methods=["POST"])
def add_to_cart():
    data = request.get_json()
    product_id = data.get("product_id")
    quantity = data.get("quantity", 1)
    cart.add_item(product_id, quantity)
    return jsonify({"message": "Item added to cart"}), 200


@app.route("/cart", methods=["GET"])
def view_cart():
    return jsonify(cart.view_cart()), 200


@app.route("/cart/checkout", methods=["POST"])
def checkout():
    data = request.get_json()
    discount_code = data.get("discount_code")
    result = cart.checkout(discount_code)
    cart.items = {}  # clear cart after checkout
    return jsonify(result), 200


@app.before_first_request
def create_tables():
    db.create_all()
    # Initialize some products and discount codes
    if not Product.query.all():
        db.session.add(Product(name="Product 1", price=10.99))
        db.session.add(Product(name="Product 2", price=5.99))
        db.session.commit()
    if not DiscountCode.query.all():
        db.session.add(DiscountCode(code="DISCOUNT10", discount_percentage=10))
        db.session.commit()


if __name__ == "__main__":
    app.run(debug=True)
