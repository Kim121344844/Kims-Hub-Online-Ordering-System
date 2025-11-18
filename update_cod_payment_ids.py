from flask import Flask
from models import db, Order
from config import Config

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

with app.app_context():
    # Update existing COD orders where payment_id is NULL
    cod_orders = Order.query.filter_by(payment_method='COD').filter(Order.payment_id.is_(None)).all()
    updated_count = 0
    for order in cod_orders:
        order.payment_id = f'cod_{order.order_id}'
        updated_count += 1
    db.session.commit()
    print(f'Updated {updated_count} COD orders with payment_id.')
