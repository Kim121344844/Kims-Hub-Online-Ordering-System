import os
import uuid
import requests
import datetime
import random
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_socketio import SocketIO, emit, join_room
from dotenv import load_dotenv
from models import db, User, Order, OTP, ChatMessage, Review
from config import Config
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message
from otp import generate_otp, send_otp_email, store_otp_in_db, send_password_reset_otp_email
from sqlalchemy import text

load_dotenv()
otp_storage = {}
users = []
all_orders = []

# Menu items with fixed prices
MENU_ITEMS = {
    'Burger': 800,
    'Pizza': 1200,
    'Tacos': 600,
    'Main Course': 1500,
    'Mexican Food': 1000,
    'Filipino Food': 500,
    'Healthy Options': 700,
    'Dessert': 400,
    'Drinks': 200
}

def _load_users_from_db():
    global users
    with app.app_context():
        try:
            users_db = User.query.all()
            users = [{'name': u.name, 'email': u.email, 'password': u.password, 'role': u.role, 'profile_picture': u.profile_picture} for u in users_db]
            print(f'Loaded {len(users)} users from database')
        except Exception as e:
            print('Error loading users from database:', e)
            users = []

app = Flask(__name__)
app.config.from_object(Config)

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = 'kimshubonlineorderingsystem@gmail.com'
app.config['MAIL_PASSWORD'] = 'frav tlep eaes xyqs'
app.config['MAIL_DEFAULT_SENDER'] = 'kimshubonlineorderingsystem@gmail.com'
app.config['UPLOAD_FOLDER'] = 'static/profile_pics'

db.init_app(app)
socketio = SocketIO(app)
mail = Mail(app)

with app.app_context():
    db.create_all()
    # Alter reviews table to allow NULL order_id if not already
    try:
        db.session.execute(text("ALTER TABLE reviews MODIFY order_id VARCHAR(50) NULL;"))
        db.session.commit()
        print('Altered reviews table to allow NULL order_id')
    except Exception as e:
        print('Alter table skipped or failed:', e)
        db.session.rollback()
    # Alter users table to add profile_picture column if not exists
    try:
        db.session.execute(text("ALTER TABLE users ADD COLUMN profile_picture VARCHAR(200) NULL;"))
        db.session.commit()
        print('Altered users table to add profile_picture column')
    except Exception as e:
        print('Alter users table skipped or failed:', e)
        db.session.rollback()
    # Create default admin user if not exists
    admin_user = User.query.filter_by(role='admin').first()
    if not admin_user:
        hashed_password = generate_password_hash('admin123', method='pbkdf2:sha256:600000', salt_length=8)
        admin_user = User(name='Admin', email='admin@kimshub.com', password=hashed_password, role='admin')
        db.session.add(admin_user)
        db.session.commit()
        print('Default admin user created: admin@kimshub.com / admin123')
    _load_users_from_db()  # Always load users from database on app start
    print('Database tables created or verified.')

# Payment API functions

def initiate_gcash_payment(amount, order_id, description):
    gcash_app_id = os.getenv('GCASH_APP_ID')
    gcash_app_secret = os.getenv('GCASH_APP_SECRET')
    return {'status': 'success', 'payment_id': f'gcash_{order_id}', 'redirect_url': f'https://gcash.com/pay/{order_id}'}

def initiate_paymaya_payment(amount, order_id, description):
    paymaya_public_key = os.getenv('PAYMAYA_PUBLIC_KEY')
    paymaya_secret_key = os.getenv('PAYMAYA_SECRET_KEY')
    return {'status': 'success', 'payment_id': f'paymaya_{order_id}', 'redirect_url': f'https://paymaya.com/pay/{order_id}'}

@app.context_processor
def inject_users():
    return {'users': users}

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/menu')
def menu():
    return render_template('menu.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].lower()
        password = request.form['password']

        if len(password) < 6:
            return render_template('login.html', error='Password length is incorrect. Minimum 6 characters required.', email=email)
        
        user = next((u for u in users if u['email'] == email), None)
        if not user:
            return render_template('login.html', error='Email not registered.', email=email)
        
        from werkzeug.security import check_password_hash
        if not check_password_hash(user['password'], password):
            return render_template('login.html', error='Password is incorrect.', email=email)

        # Check if user is admin
        if user.get('role') == 'admin':
            # Admin login directly without OTP
            session['user'] = email
            flash("Login successful!", "success")
            return redirect(url_for('admin_dashboard'))
        else:
            # Regular user: Generate and send login OTP
            otp = generate_otp()
            stored_otp = store_otp_in_db(email, otp)

            if not send_otp_email(email, user['name'], otp):
                db.session.delete(stored_otp)
                db.session.commit()
                return render_template('login.html', error='Failed to send OTP. Please try again later.', email=email)

            # Redirect to login page with OTP modal
            return redirect(url_for('login', otp_required='true', email=email))

    return render_template('login.html')

@app.route('/verify_login_otp/<email>', methods=['GET', 'POST'])
def verify_login_otp(email):
    if request.method == 'POST':
        otp_input = request.form['otp']
        from otp import verify_otp_from_db
        success, message = verify_otp_from_db(email, otp_input)
        if success:
            session['user'] = email
            return jsonify({'success': True, 'redirect': url_for('dashboard')})
        else:
            return jsonify({'success': False, 'message': message})

    return render_template('verify_login_otp.html', email=email)



@app.route('/reset_password/<email>', methods=['GET', 'POST'])
def reset_password(email):
    if request.method == 'POST':
        otp_input = request.form['otp']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']

        if len(new_password) < 6:
            flash('Password length is incorrect. Minimum 6 characters required.', 'error')
            return render_template('reset_password.html', email=email)

        if new_password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('reset_password.html', email=email)

        from otp import verify_password_reset_otp
        success, message = verify_password_reset_otp(email, otp_input)
        if not success:
            flash(message, 'error')
            return render_template('reset_password.html', email=email)

        # Update password
        user = next((u for u in users if u['email'] == email), None)
        if user:
            from werkzeug.security import generate_password_hash
            hashed_password = generate_password_hash(new_password, method='pbkdf2:sha256:600000', salt_length=8)
            # Update in database
            db_user = User.query.filter_by(email=email).first()
            if db_user:
                db_user.password = hashed_password
                db.session.commit()
                # Reload users from database
                _load_users_from_db()
                flash('Password reset successful! Please login with your new password.', 'success')
                return redirect(url_for('login'))
            else:
                flash('User not found.', 'error')
        else:
            flash('User not found.', 'error')

    return render_template('reset_password.html', email=email)


@app.route('/dashboard')
def dashboard():
    user_email = session.get('user')
    if user_email:

        # Find user name from registered users

        user = next((u for u in users if u['email'] == user_email), None)
        user_name = user['name'] if user else 'User'
    else:
        user_name = 'Guest'
        user_email = 'guest@example.com'
    favorites = session.get('favorites', [
        {'name': 'Burger', 'image': 'images/Burger.jpg'},
        {'name': 'Pizza', 'image': 'images/Pizza.jpg'}
    ])
    cart = session.get('cart', [])
    cart_total = sum(item['price'] * item['quantity'] for item in cart)

    # Calculate user stats

    user_orders = [order for order in all_orders if order.get('user_email') == user_email]
    total_orders = len(user_orders)
    total_spent = sum(order['total'] for order in user_orders)

    # Favorite category

    item_counts = {}
    for order in user_orders:
        for item in order['items']:
            item_counts[item] = item_counts.get(item, 0) + 1
    favorite_category = max(item_counts, key=item_counts.get) if item_counts else 'None'

    # Recent orders
    recent_orders = user_orders[-3:] if user_orders else []

    # Recommendations
    recommendations = [
        {'name': 'Chicken Adobo', 'image': 'images/Chicken Adobo.jpg', 'price': 120.00},
        {'name': 'Sinigang', 'image': 'images/Sinigang.jpg', 'price': 150.00},
        {'name': 'Tacos', 'image': 'images/Tacos.jpg', 'price': 100.00}
    ]

    # Find admin email for chat
    admin_email = next((u['email'] for u in users if u.get('role') == 'admin'), None)

    return render_template('dashboard.html', user=user, user_name=user_name, user_email=user_email, favorites=favorites, cart=cart,
                           cart_total=cart_total, total_orders=total_orders, total_spent=total_spent, favorite_category=favorite_category,
                           recent_orders=recent_orders, recommendations=recommendations, admin_email=admin_email)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email'].lower()
        password = request.form['password']
        if len(password) < 6:
            return render_template('signup.html', error='Password length is incorrect. Minimum 6 characters required.', name=name, email=email)
        
        # Check if user already exists
        if any(user['email'] == email for user in users):
            return render_template('signup.html', error='Email already registered', name=name, email=email)
        
        # Hash password
        from werkzeug.security import generate_password_hash
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256:600000', salt_length=8)
        # Insert into database
        try:
            new_user = User(name=name, email=email, password=hashed_password, role='user')
            db.session.add(new_user)
            db.session.commit()
            # Reload users from database
            _load_users_from_db()
        except Exception as e:
            print('Error saving user to database:', e)
            db.session.rollback()
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/logout', methods=['GET', 'POST'])
def logout():
    if 'user' not in session:
        return redirect(url_for('login', error='You are not logged in.'))
    if request.method == 'POST':
        session.pop('user', None)
        return redirect(url_for('home'))
    return render_template('logout_confirm.html')

@app.route('/add_item', methods=['POST'])
def add_item():
    item_name = request.form['item_name']
    quantity = int(request.form.get('quantity', 1))

    # Validate quantity
    if quantity <= 0 or quantity > 10:
        flash('Please select a quantity between 1 and 10.', 'error')
        return redirect(url_for('menu'))

    # Validate item name: must be on the menu
    if not item_name.strip() or item_name not in MENU_ITEMS:
        flash('Invalid item. Only menu items are allowed.', 'error')
        return redirect(url_for('menu'))

    # Get price from menu
    item_price = MENU_ITEMS[item_name]

    cart = session.get('cart', [])

    # Check if item already exists
    existing_item = next((item for item in cart if item['name'] == item_name), None)
    if existing_item:
        existing_item['quantity'] += quantity
    else:
        cart.append({'name': item_name, 'price': item_price, 'quantity': quantity})
    session['cart'] = cart
    flash(f'Added {quantity} x {item_name} to cart.', 'success')
    return redirect(url_for('menu'))

@app.route('/remove_item/<int:index>')
def remove_item(index):
    cart = session.get('cart', [])
    if 0 <= index < len(cart):
        if cart[index]['quantity'] > 1:
            cart[index]['quantity'] -= 1
        else:
            cart.pop(index)
        session['cart'] = cart
    return redirect(url_for('dashboard'))

@app.route('/remove_favorite/<int:index>')
def remove_favorite(index):
    favorites = session.get('favorites', [])
    if 0 <= index < len(favorites):
        favorites.pop(index)
        session['favorites'] = favorites
    return redirect(url_for('dashboard'))

@app.route('/reorder/<order_id>')
def reorder(order_id):
    order = next((o for o in all_orders if o['order_id'] == order_id), None)
    if order and order['user_email'] == session.get('user'):
        cart = session.get('cart', [])
        for item_name in order['items']:

            # Simple reorder: add one of each item
            cart.append({'name': item_name, 'price': 100.0, 'quantity': 1})
        session['cart'] = cart
    return redirect(url_for('dashboard'))

@app.route('/add_item_payment', methods=['POST'])
def add_item_payment():
    item_name = request.form['item_name']
    quantity = int(request.form.get('quantity', 1))

    # Validate item name: must be on the menu
    if not item_name.strip() or item_name not in MENU_ITEMS:
        return {'success': False, 'error': 'Invalid item. Only menu items are allowed.'}, 400

    # Get price from menu
    item_price = MENU_ITEMS[item_name]

    cart = session.get('cart', [])

    # Check if item already exists
    existing_item = next((item for item in cart if item['name'] == item_name), None)
    if existing_item:
        existing_item['quantity'] += quantity
    else:
        cart.append({'name': item_name, 'price': item_price, 'quantity': quantity})
    session['cart'] = cart
    total = sum(item['price'] * item['quantity'] for item in cart)
    return {'success': True, 'cart': cart, 'total': total}

@app.route('/edit_item_payment/<int:index>', methods=['POST'])
def edit_item_payment(index):
    cart = session.get('cart', [])
    if 0 <= index < len(cart):
        item_name = request.form['item_name']
        quantity = int(request.form.get('quantity', cart[index]['quantity']))

        # Validate item name: must be on the menu
        if not item_name.strip() or item_name not in MENU_ITEMS:
            return {'success': False, 'error': 'Invalid item. Only menu items are allowed.'}, 400

        # Get price from menu
        item_price = MENU_ITEMS[item_name]

        cart[index] = {'name': item_name, 'price': item_price, 'quantity': quantity}
        session['cart'] = cart
    total = sum(item['price'] * item['quantity'] for item in cart)
    return {'success': True, 'cart': cart, 'total': total}

@app.route('/remove_item_payment/<int:index>', methods=['POST'])
def remove_item_payment(index):
    cart = session.get('cart', [])
    if 0 <= index < len(cart):
        if cart[index]['quantity'] > 1:
            cart[index]['quantity'] -= 1
        else:
            cart.pop(index)
        session['cart'] = cart
    total = sum(item['price'] * item['quantity'] for item in cart)
    return {'success': True, 'cart': cart, 'total': total}

@app.route('/payment', methods=['GET', 'POST'])
def payment():
    if 'user' not in session:
        return redirect(url_for('login'))
    cart = session.get('cart', [])
    if not cart:
        return redirect(url_for('dashboard'))
    total = sum(item['price'] * item['quantity'] for item in cart)
    if request.method == 'POST':
        payment_method = request.form['payment_method']
        email = request.form.get('email')
        phone = request.form.get('phone')
        address = request.form.get('address')
        postal = request.form.get('postal')
        city = request.form.get('city')
        if not email or not phone or not address or not postal or not city:
            return render_template('payment.html', cart=cart, error='Please provide email, phone, home address, postal number, and city for all payment methods.')
        total = sum(item['price'] * item['quantity'] for item in cart)
        order_id = str(uuid.uuid4())
        description = f"Order {order_id} for {session.get('user')}"

        if payment_method == 'GCash':
            payment_response = initiate_gcash_payment(total, order_id, description)
            if payment_response['status'] == 'success':
                status = 'Processing'
                payment_id = payment_response['payment_id']
            else:
                return render_template('payment.html', cart=cart, error='GCash payment initiation failed.')
        elif payment_method == 'PayMaya':
            payment_response = initiate_paymaya_payment(total, order_id, description)
            if payment_response['status'] == 'success':
                status = 'Processing'
                payment_id = payment_response['payment_id']
            else:
                return render_template('payment.html', cart=cart, error='PayMaya payment initiation failed.')
        else:  # COD
            status = 'Processing'
            payment_id = f'cod_{order_id}'

        # Store order details
        order = {
            'order_id': order_id,
            'user_email': session.get('user'),
            'user_name': next((u['name'] for u in users if u['email'] == session.get('user')), 'User'),
            'phone': phone,
            'address': address,
            'postal': postal,
            'city': city,
            'date': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),  # Use current date and time
            'processing_start': datetime.datetime.now(),
            'items': [item['name'] for item in cart],
            'total': total,
            'payment_method': payment_method,
            'payment_id': payment_id,
            'status': status
        }
        # Insert order into database
        try:
            new_order = Order(
                order_id=order_id,
                user_email=session.get('user'),
                user_name=order['user_name'],
                phone=phone,
                address=address,
                postal=postal,
                city=city,
                date=order['date'],
                items=','.join(order['items']),
                total=total,
                payment_method=payment_method,
                payment_id=payment_id,
                status=status
            )
            db.session.add(new_order)
            db.session.commit()
            # Reload orders from database
            _load_orders_from_db()
        except Exception as e:
            print('Error saving order to database:', e)
            db.session.rollback()
        receipt = {
            'order_id': order_id,
            'items': cart,
            'total': total,
            'payment_method': payment_method,
            'email': email,
            'phone': phone,
            'address': address,
            'postal': postal,
            'city': city,
            'date': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),  # Use current date and time
            'status': status
        }
        session['receipt'] = receipt
        session['cart'] = []  # Clear cart after payment
        return redirect(url_for('receipt', order_id=order_id))
    return render_template('payment.html', cart=cart, total=total)

@app.route('/receipt')
def receipt():
    if 'user' not in session:
        return redirect(url_for('login'))
    receipt = session.get('receipt')
    if not receipt:
        return redirect(url_for('dashboard'))
    return render_template('receipt.html', receipt=receipt)

def _load_orders_from_db():
    global all_orders
    with app.app_context():
        try:
            orders_db = Order.query.all()
            all_orders = []
            for o in orders_db:
                all_orders.append({
                    'order_id': o.order_id,
                    'user_email': o.user_email,
                    'user_name': o.user_name,
                    'phone': o.phone,
                    'address': o.address,
                    'postal': o.postal,
                    'city': o.city,
                    'date': o.date,
                    'processing_start': datetime.datetime.strptime(o.date, '%Y-%m-%d %H:%M:%S') if isinstance(o.date, str) else o.date,
                    'items': o.items.split(',') if o.items else [],
                    'total': float(o.total),
                    'payment_method': o.payment_method,
                    'payment_id': o.payment_id,
                    'status': o.status
                })
            print(f'Loaded {len(all_orders)} orders from database')
        except Exception as e:
            print('Error loading orders from database:', e)
            all_orders = []

_load_orders_from_db()

@app.route('/admin_dashboard')
def admin_dashboard():
    user_email = session.get('user')
    if not user_email:
        return redirect(url_for('login'))
    user = next((u for u in users if u['email'] == user_email), None)
    if not user or user.get('role') != 'admin':
        return redirect(url_for('dashboard'))
    
    # Mock aggregated data for admin
    total_users = len(users)
    total_orders = len(all_orders)
    total_revenue = sum(order['total'] for order in all_orders)

    # Calculate orders per user
    orders_per_user = {}
    for order in all_orders:
        email = order['user_email']
        if email not in orders_per_user:
            orders_per_user[email] = 0
        orders_per_user[email] += 1
    return render_template('admin_dashboard.html', users=users, total_users=total_users, total_orders=total_orders, total_revenue=total_revenue, all_orders=all_orders, orders_per_user=orders_per_user, user_email=user_email)

@app.route('/api/orders')
def api_orders():
    user_email = session.get('user')
    if not user_email:
        return {'error': 'Not logged in'}, 401
    user = next((u for u in users if u['email'] == user_email), None)
    if not user or user.get('role') != 'admin':
        return {'error': 'Unauthorized'}, 403
    total_revenue = sum(order['total'] for order in all_orders)
    return {'orders': all_orders, 'users': users, 'total_users': len(users), 'total_orders': len(all_orders), 'total_revenue': total_revenue}

@app.route('/api/user_orders')
def api_user_orders():
    user_email = session.get('user')
    if not user_email:
        return {'error': 'Not logged in'}, 401
    # All user orders for notifications
    all_user_orders = [order for order in all_orders if order.get('user_email') == user_email]
    # Dynamic order history for the user (exclude cancelled orders)
    user_orders = [order for order in all_user_orders if order.get('status') != 'Cancelled']
    order_history = [
        {'order_id': order['order_id'], 'date': order['date'], 'items': order['items'], 'status': order['status']}
        for order in user_orders
    ]
    # Dynamic notifications based on all user orders
    notifications = []
    if all_user_orders:
        recent_order = all_user_orders[-1]
        if recent_order['status'] == 'Delivered':
            notifications.append('Rate your recent order.')
        elif recent_order['status'] == 'Processing':
            notifications.append('Your order is being processed.')
        elif recent_order['status'] == 'Paid':
            notifications.append('Your order has been confirmed!')
        elif recent_order['status'] == 'Cancelled':
            notifications.append('Your order has been cancelled.')
    else:
        notifications.append('Welcome! Start by browsing our menu.')
    notifications.append('New promotion: 20% off on desserts.')
    return {'order_history': order_history, 'notifications': notifications}

@app.route('/cancel_order/<order_id>', methods=['POST'])
def cancel_order(order_id):
    user_email = session.get('user')
    if not user_email:
        return {'error': 'Not logged in'}, 401
    user = next((u for u in users if u['email'] == user_email), None)
    if not user or user.get('role') != 'admin':
        return {'error': 'Unauthorized'}, 403
    order = next((o for o in all_orders if o['order_id'] == order_id), None)
    if order and order['status'] != 'Cancelled':
        order['status'] = 'Cancelled'
        # Update database
        try:
            order_db = Order.query.filter_by(order_id=order_id).first()
            if order_db:
                order_db.status = 'Cancelled'
                db.session.commit()
        except Exception as e:
            print('Error updating order status in database:', e)
            db.session.rollback()

        # Real time updates
        socketio.emit('order_update', {'order_id': order_id, 'status': 'Cancelled', 'user_email': order['user_email']})
        return {'success': True}
    return {'error': 'Invalid order ID or status'}, 400

@app.route('/remove_order/<order_id>', methods=['POST'])
def remove_order(order_id):
    user_email = session.get('user')
    if not user_email:
        return {'error': 'Not logged in'}, 401
    user = next((u for u in users if u['email'] == user_email), None)
    if not user or user.get('role') != 'admin':
        return {'error': 'Unauthorized'}, 403
    order = next((o for o in all_orders if o['order_id'] == order_id), None)
    if order:
        # Delete from database
        try:
            order_db = Order.query.filter_by(order_id=order_id).first()
            if order_db:
                db.session.delete(order_db)
                db.session.commit()
                # Reload orders from database
                _load_orders_from_db()
        except Exception as e:
            print('Error deleting order from database:', e)
            db.session.rollback()
            return {'error': 'Database error'}, 500

        # Real time updates
        socketio.emit('order_update', {'order_id': order_id, 'removed': True, 'user_email': order['user_email']})
        return {'success': True}
    return {'error': 'Order not found'}, 404

@app.route('/approve_order/<order_id>', methods=['POST'])
def approve_order(order_id):
    user_email = session.get('user')
    if not user_email:
        return {'error': 'Not logged in'}, 401
    user = next((u for u in users if u['email'] == user_email), None)
    if not user or user.get('role') != 'admin':
        return {'error': 'Unauthorized'}, 403
    order = next((o for o in all_orders if o['order_id'] == order_id), None)
    if order and order['status'] == 'Processing':
        order['status'] = 'Paid'
        # Update database Payment status
        try:
            order_db = Order.query.filter_by(order_id=order_id).first()
            if order_db:
                order_db.status = 'Paid'
                db.session.commit()
        except Exception as e:
            print('Error updating order status in database:', e)
            db.session.rollback()
        # Emit real-time updates
        socketio.emit('order_update', {'order_id': order_id, 'status': 'Paid', 'user_email': order['user_email']})
        return {'success': True}
    return {'error': 'Invalid order ID or status'}, 400

@app.route('/update_order_status/<order_id>/<status>', methods=['POST'])
def update_order_status(order_id, status):
    user_email = session.get('user')
    if not user_email:
        return {'error': 'Not logged in'}, 401
    user = next((u for u in users if u['email'] == user_email), None)
    if not user or user.get('role') != 'admin':
        return {'error': 'Unauthorized'}, 403
    order = next((o for o in all_orders if o['order_id'] == order_id), None)
    if not order:
        return {'error': 'Order not found'}, 404

    # Define valid status transitions
    valid_transitions = {
        'Paid': 'Preparing',
        'Preparing': 'Cooking',
        'Cooking': 'On the way',
        'On the way': 'Delivered'
    }

    if order['status'] not in valid_transitions or valid_transitions[order['status']] != status:
        return {'error': 'Invalid status transition'}, 400

    # Update status in memory
    order['status'] = status

    # Update database
    try:
        order_db = Order.query.filter_by(order_id=order_id).first()
        if order_db:
            order_db.status = status
            db.session.commit()
    except Exception as e:
        print('Error updating order status in database:', e)
        db.session.rollback()
        return {'error': 'Database error'}, 500

    # Emit real-time updates
    socketio.emit('order_update', {'order_id': order_id, 'status': status, 'user_email': order['user_email']})
    return {'success': True}

@app.route('/edit_order/<order_id>', methods=['GET', 'POST'])
def edit_order(order_id):
    user_email = session.get('user')
    if not user_email:
        return {'error': 'Not logged in'}, 401
    user = next((u for u in users if u['email'] == user_email), None)
    if not user or user.get('role') != 'admin':
        return {'error': 'Unauthorized'}, 403
    order = next((o for o in all_orders if o['order_id'] == order_id), None)
    if not order:
        return {'error': 'Order not found'}, 404
    if request.method == 'POST':
        new_user_name = request.form.get('user_name', order['user_name'])
        new_user_email = request.form.get('user_email', order['user_email'])
        # ORDER DETAILS UPDATE
        order['user_name'] = new_user_name
        order['user_email'] = new_user_email
        order['phone'] = request.form.get('phone', order['phone'])
        order['address'] = request.form.get('address', order['address'])
        order['postal'] = request.form.get('postal', order['postal'])
        order['city'] = request.form.get('city', order['city'])
        order['items'] = request.form.getlist('items') 
        order['total'] = float(request.form.get('total', order['total']))
        order['payment_method'] = request.form.get('payment_method', order['payment_method'])
        # UPDATE DATABASE
        try:
            db_order = Order.query.filter_by(order_id=order_id).first()
            if db_order:
                db_order.user_name = order['user_name']
                db_order.user_email = order['user_email']
                db_order.phone = order['phone']
                db_order.address = order['address']
                db_order.postal = order['postal']
                db_order.city = order['city']
                db_order.items = ','.join(order['items'])
                db_order.total = order['total']
                db_order.payment_method = order['payment_method']
                db.session.commit()

            if new_user_email != order['user_email'] or new_user_name != order['user_name']:
                user_db = User.query.filter_by(email=order['user_email']).first()
                if user_db:
                    user_db.email = new_user_email
                    user_db.name = new_user_name
                    db.session.commit()
                
                    _load_users_from_db()
        except Exception as e:
            print('Error updating order/user in database:', e)
            db.session.rollback()
            return {'error': 'Database error'}, 500
        socketio.emit('order_update', {'order_id': order_id, 'status': order['status'], 'user_email': order['user_email']})
        return redirect(url_for('admin_dashboard'))
    return render_template('edit_order.html', order=order)

@socketio.on('connect')
def handle_connect():
    user_email = session.get('user')
    if user_email:
        join_room(user_email)
        user = next((u for u in users if u['email'] == user_email), None)
        if user and user.get('role') == 'admin':
            join_room(user_email)
        print(f'User {user_email} connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

@app.route('/payment_status/<order_id>')
def payment_status(order_id):
    order = next((o for o in all_orders if o.get('order_id') == order_id), None)
    if not order:
        return jsonify({'error': 'Order not found'}), 404
    if order['status'] == 'Processing' and order.get('processing_start'):
        elapsed = datetime.datetime.now() - order['processing_start']
        if elapsed.total_seconds() > 300:
            order['status'] = 'Paid'
            socketio.emit('order_update', {'order_id': order_id, 'status': 'Paid', 'user_email': order['user_email']})
    return jsonify({'status': order['status']})

@app.route('/edit_profile', methods=['POST'])
def edit_profile():
    user_email = session.get('user')
    if not user_email:
        return jsonify({'message': 'Not logged in'}), 401

    new_name = request.form.get('name')
    new_email = request.form.get('email')

    if not new_name or not new_email:
        return jsonify({'message': 'Name and email are required'}), 400

    existing_user = User.query.filter_by(email=new_email).first()
    if existing_user and existing_user.email != user_email:
        return jsonify({'message': 'Email already in use'}), 400

    user = User.query.filter_by(email=user_email).first()
    if user:
        user.name = new_name
        user.email = new_email

        # Handle profile picture upload
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and file.filename:
                filename = secure_filename(file.filename)
                unique_filename = f"{uuid.uuid4()}_{filename}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                file.save(file_path)
                user.profile_picture = unique_filename

        db.session.commit()
        session['user'] = new_email
        _load_users_from_db()
        return jsonify({'message': 'Profile updated successfully'}), 200
    else:
        return jsonify({'message': 'User not found'}), 404

@app.route('/remove_user/<email>', methods=['POST'])
def remove_user(email):
    user_email = session.get('user')
    if not user_email:
        return {'error': 'Not logged in'}, 401
    user = next((u for u in users if u['email'] == user_email), None)
    if not user or user.get('role') != 'admin':
        return {'error': 'Unauthorized'}, 403
    # Prevent admin from removing themselves
    if email == user_email:
        return {'error': 'Cannot remove yourself'}, 400
    # Find and remove user from database
    try:
        user_to_remove = User.query.filter_by(email=email).first()
        if user_to_remove:
            # Also remove all orders associated with this user
            orders_to_remove = Order.query.filter_by(user_email=email).all()
            for order in orders_to_remove:
                db.session.delete(order)
            db.session.delete(user_to_remove)
            db.session.commit()
            # Reload users and orders from database
            _load_users_from_db()
            _load_orders_from_db()
            return {'success': True}
        else:
            return {'error': 'User not found'}, 404
    except Exception as e:
        print('Error removing user from database:', e)
        db.session.rollback()
        return {'error': 'Database error'}, 500

@app.route('/remove_favorite_ajax/<fav_id>', methods=['POST'])
def remove_favorite_ajax(fav_id):
    user_email = session.get('user')
    if not user_email:
        return jsonify({'message': 'Not logged in'}), 401
    return jsonify({'message': 'Favorite removed successfully'}), 200

@app.route('/send_message', methods=['POST'])
def send_message():
    user_email = session.get('user')
    if not user_email:
        return jsonify({'error': 'Not logged in'}), 401

    data = request.get_json()
    receiver_email = data.get('receiver_email')
    message = data.get('message')

    if not receiver_email or not message:
        return jsonify({'error': 'Receiver email and message are required'}), 400

    # Validate receiver exists
    receiver = next((u for u in users if u['email'] == receiver_email), None)
    if not receiver:
        return jsonify({'error': 'Receiver not found'}), 404

    # Determine the room to emit to
    admin_email = next((u['email'] for u in users if u.get('role') == 'admin'), None)
    if receiver_email == admin_email:
        room = admin_email
    else:
        room = receiver_email

    # Save message to DB
    try:
        new_message = ChatMessage(sender_email=user_email, receiver_email=receiver_email, message=message)
        db.session.add(new_message)
        db.session.commit()
        # Emit to receiver room
        socketio.emit('receive_message', {
            'sender_email': user_email,
            'message': message,
            'timestamp': new_message.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        }, room=room)
        return jsonify({'success': True}), 200
    except Exception as e:
        print('Error sending message:', e)
        db.session.rollback()
        return jsonify({'error': 'Database error'}), 500

@app.route('/get_messages')
def get_messages():
    user_email = session.get('user')
    if not user_email:
        return jsonify({'error': 'Not logged in'}), 401

    # Get messages where user is sender or receiver
    try:
        messages = ChatMessage.query.filter(
            ((ChatMessage.sender_email == user_email) | (ChatMessage.receiver_email == user_email))
        ).order_by(ChatMessage.timestamp).all()
        message_list = [{
            'id': msg.id,
            'sender_email': msg.sender_email,
            'receiver_email': msg.receiver_email,
            'message': msg.message,
            'timestamp': msg.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'is_read': msg.is_read
        } for msg in messages]
        return jsonify({'messages': message_list}), 200
    except Exception as e:
        print('Error fetching messages:', e)
        return jsonify({'error': 'Database error'}), 500

@socketio.on('send_message')
def handle_send_message(data):
    user_email = session.get('user')
    if not user_email:
        return
    receiver_email = data.get('receiver_email')
    message = data.get('message')
    if receiver_email and message:
        # Determine the room to emit to
        admin_email = next((u['email'] for u in users if u.get('role') == 'admin'), None)
        if receiver_email == admin_email:
            room = admin_email
        else:
            room = receiver_email
        # Save and emit as above
        try:
            new_message = ChatMessage(sender_email=user_email, receiver_email=receiver_email, message=message)
            db.session.add(new_message)
            db.session.commit()
            socketio.emit('receive_message', {
                'sender_email': user_email,
                'message': message,
                'timestamp': new_message.timestamp.strftime('%Y-%m-%d %H:%M:%S')
            }, room=room)
        except Exception as e:
            print('Error in socket send message:', e)
            db.session.rollback()

@app.route('/forgot_password', methods=['POST'])
def forgot_password():
    email = request.form.get('email')

    if not email:
        return jsonify({'message': 'Email is required.'}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'message': 'Email not registered.'}), 400

    otp = generate_otp()
    store_otp_in_db(email, otp)

    if send_password_reset_otp_email(email, user.name, otp):
        return jsonify({'message': 'Reset code sent to your email.'}), 200
    else:
        return jsonify({'message': 'Failed to send email. Please try again.'}), 500

@app.route('/submit_review', methods=['POST'])
def submit_review():
    user_email = session.get('user')
    if not user_email:
        return jsonify({'error': 'Not logged in'}), 401

    data = request.get_json()
    order_id = data.get('order_id')
    rating = data.get('rating')
    comment = data.get('comment', '').strip()

    if not rating:
        return jsonify({'error': 'Rating is required'}), 400

    if rating < 1 or rating > 5:
        return jsonify({'error': 'Rating must be between 1 and 5'}), 400

    # If order_id is provided, validate it (for order-specific reviews)
    if order_id:
        # Check if order exists and belongs to user and is delivered
        order = next((o for o in all_orders if o['order_id'] == order_id and o['user_email'] == user_email), None)
        if not order:
            return jsonify({'error': 'Order not found'}), 404

        if order['status'] != 'Delivered':
            return jsonify({'error': 'Only delivered orders can be reviewed'}), 400

        # Check if review already exists for this order
        existing_review = Review.query.filter_by(order_id=order_id, user_email=user_email).first()
        if existing_review:
            return jsonify({'error': 'Review already submitted for this order'}), 400
    else:
        # General review, no order_id
        pass

    # Save review
    try:
        new_review = Review(order_id=order_id, user_email=user_email, rating=rating, comment=comment)
        db.session.add(new_review)
        db.session.commit()
        return jsonify({'success': True}), 200
    except Exception as e:
        print('Error submitting review:', e)
        db.session.rollback()
        return jsonify({'error': 'Database error'}), 500

@app.route('/api/user_reviews')
def api_user_reviews():
    user_email = session.get('user')
    if not user_email:
        return jsonify({'error': 'Not logged in'}), 401

    try:
        reviews = Review.query.filter_by(user_email=user_email).order_by(Review.timestamp.desc()).all()
        review_list = [{
            'id': r.id,
            'order_id': r.order_id,
            'rating': r.rating,
            'comment': r.comment,
            'approved': r.approved,
            'timestamp': r.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        } for r in reviews]
        return jsonify({'reviews': review_list}), 200
    except Exception as e:
        print('Error fetching user reviews:', e)
        return jsonify({'error': 'Database error'}), 500

@app.route('/api/approved_reviews')
def api_approved_reviews():
    try:
        reviews = Review.query.filter_by(approved=True).order_by(Review.timestamp.desc()).all()
        review_list = [{
            'rating': r.rating,
            'comment': r.comment,
            'user_email': r.user_email,
            'timestamp': r.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        } for r in reviews]
        return jsonify({'reviews': review_list}), 200
    except Exception as e:
        print('Error fetching approved reviews:', e)
        return jsonify({'error': 'Database error'}), 500

@app.route('/api/reviews')
def api_reviews():
    user_email = session.get('user')
    if not user_email:
        return jsonify({'error': 'Not logged in'}), 401
    user = next((u for u in users if u['email'] == user_email), None)
    if not user or user.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        reviews = Review.query.order_by(Review.timestamp.desc()).all()
        review_list = [{
            'id': r.id,
            'order_id': r.order_id,
            'user_email': r.user_email,
            'rating': r.rating,
            'comment': r.comment,
            'approved': r.approved,
            'timestamp': r.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        } for r in reviews]
        return jsonify({'reviews': review_list}), 200
    except Exception as e:
        print('Error fetching reviews:', e)
        return jsonify({'error': 'Database error'}), 500

@app.route('/approve_review/<int:review_id>', methods=['POST'])
def approve_review(review_id):
    user_email = session.get('user')
    if not user_email:
        return jsonify({'error': 'Not logged in'}), 401
    user = next((u for u in users if u['email'] == user_email), None)
    if not user or user.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        review = Review.query.get(review_id)
        if not review:
            return jsonify({'error': 'Review not found'}), 404
        review.approved = True
        db.session.commit()
        return jsonify({'success': True}), 200
    except Exception as e:
        print('Error approving review:', e)
        db.session.rollback()
        return jsonify({'error': 'Database error'}), 500

@app.route('/delete_review/<int:review_id>', methods=['POST'])
def delete_review(review_id):
    user_email = session.get('user')
    if not user_email:
        return jsonify({'error': 'Not logged in'}), 401
    user = next((u for u in users if u['email'] == user_email), None)
    if not user or user.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        review = Review.query.get(review_id)
        if not review:
            return jsonify({'error': 'Review not found'}), 404
        db.session.delete(review)
        db.session.commit()
        return jsonify({'success': True}), 200
    except Exception as e:
        print('Error deleting review:', e)
        db.session.rollback()
        return jsonify({'error': 'Database error'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.getenv("PORT", 5000)))
