from flask import Flask
from models import db, Order
from config import Config

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

with app.app_context():
    orders = Order.query.all()
    print('Total orders:', len(orders))
    for o in orders:
        print(f'Order {o.order_id}: method={o.payment_method}, id={o.payment_id}')
