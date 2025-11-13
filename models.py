from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), default='user')

    def __repr__(self):
        return f'<User {self.email}>'

class OTP(db.Model):
    __tablename__ = 'otps'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False)
    otp_code = db.Column(db.String(6), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f'<OTP {self.email} - {self.otp_code}>'

class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.String(50), unique=True, nullable=False)
    user_email = db.Column(db.String(120), nullable=False)
    user_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    address = db.Column(db.String(200))
    postal = db.Column(db.String(20))
    city = db.Column(db.String(100))
    date = db.Column(db.String(50))
    items = db.Column(db.Text)
    total = db.Column(db.Float)
    payment_method = db.Column(db.String(50))
    payment_id = db.Column(db.String(100))
    status = db.Column(db.String(50), default='Processing')

    def __repr__(self):
        return f'<Order {self.order_id}>'
