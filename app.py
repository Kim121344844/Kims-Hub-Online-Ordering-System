import os
import uuid
import requests
import datetime
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_socketio import SocketIO, emit, join_room
from dotenv import load_dotenv

load_dotenv()
try:
    import mysql.connector
    from mysql.connector import Error
except Exception:
    mysql = None
    Error = Exception

db_config = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'kims') 
}

conn = None
cursor = None
try:
    if 'mysql' in globals() and mysql is not None:
        conn = mysql.connector.connect(**db_config)
        if conn.is_connected():
            cursor = conn.cursor(dictionary=True)
            print('Connected to MySQL database')
    else:
        print('mysql.connector not installed; database connection skipped')
except Exception as e:
    print('Error connecting to database:', e)
    conn = None
    cursor = None

app = Flask(__name__)
app.secret_key = 'your_secret_key_here' 
socketio = SocketIO(app)

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
users = []

def _load_users_from_db():
    global users
    try:
        if cursor:
            cursor.execute("SELECT name, email, password, role FROM users")
            rows = cursor.fetchall()
            loaded = []
            for r in rows:
                loaded.append({
                    'name': r.get('name') or r.get('full_name') or r.get('username') or 'User',
                    'email': r.get('email'),
                    'password': r.get('password'),
                    'role': r.get('role', 'user')
                })
            users = loaded
            print(f'Loaded {len(users)} users from database')
        else:
            print('DB cursor not available; users list is empty')
            users = []
    except Exception as e:
        print('Error loading users from database:', e)
        users = []

_load_users_from_db()

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
        
        # Find user by email

        user = next((u for u in users if u['email'] == email), None)
        if user:
            from werkzeug.security import check_password_hash
            if check_password_hash(user['password'], password):
                session['user'] = email
                if user.get('role') == 'admin':
                    return redirect(url_for('admin_dashboard'))
                else:
                    return redirect(url_for('dashboard'))
            else:
                return render_template('login.html', error='Password is incorrect.', email=email)
        else:
            return render_template('login.html', error='Email not registered.', email=email)
    return render_template('login.html')

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
    favorites = [
        {'name': 'Burger', 'image': 'images/Burger.jpg'},
        {'name': 'Pizza', 'image': 'images/Pizza.jpg'}
    ]
    cart = session.get('cart', [])

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

    return render_template('dashboard.html', user_name=user_name, user_email=user_email, favorites=favorites, cart=cart,
                           total_orders=total_orders, total_spent=total_spent, favorite_category=favorite_category,
                           recent_orders=recent_orders, recommendations=recommendations)

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
            if cursor:
                cursor.execute("""
                INSERT INTO users (name, email, password, role)
                VALUES (%s, %s, %s, %s)
                """, (name, email, hashed_password, 'user'))
                conn.commit()
                # Reload users from database
                _load_users_from_db()
            else:
                # Fallback to in-memory if DB not available
                users.append({'name': name, 'email': email, 'password': hashed_password, 'role': 'user'})
        except Exception as e:
            print('Error saving user to database:', e)
            # Fallback to in-memory
            users.append({'name': name, 'email': email, 'password': hashed_password, 'role': 'user'})
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
    item_price = float(request.form['item_price'])
    quantity = int(request.form.get('quantity', 1))
    cart = session.get('cart', [])

    # Check if item already exists
    existing_item = next((item for item in cart if item['name'] == item_name), None)
    if existing_item:
        existing_item['quantity'] += quantity
    else:
        cart.append({'name': item_name, 'price': item_price, 'quantity': quantity})
    session['cart'] = cart
    return redirect(url_for('dashboard'))

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
    item_price = float(request.form['item_price'])
    quantity = int(request.form.get('quantity', 1))
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
        item_price = float(request.form['item_price'])
        quantity = int(request.form.get('quantity', cart[index]['quantity']))
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
            payment_id = None

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
            if cursor:
                cursor.execute("""
                INSERT INTO orders (order_id, user_email, user_name, phone, address, postal, city, date, items, total, payment_method, payment_id, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (order_id, session.get('user'), order['user_name'], phone, address, postal, city, order['date'], ','.join(order['items']), total, payment_method, payment_id, status))
                conn.commit()
                # Reload orders from database
                _load_orders_from_db()
            else:
                # Fallback to in-memory if DB not available
                all_orders.append(order)
        except Exception as e:
            print('Error saving order to database:', e)
            # Fallback to in-memory
            all_orders.append(order)
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
        if payment_method in ['GCash', 'PayMaya']:
            return redirect(url_for('payment', order_id=order_id))
        else:
            return redirect(url_for('receipt', order_id=order_id))
    return render_template('payment.html', cart=cart)

@app.route('/receipt')
def receipt():
    if 'user' not in session:
        return redirect(url_for('login'))
    receipt = session.get('receipt')
    if not receipt:
        return redirect(url_for('dashboard'))
    return render_template('receipt.html', receipt=receipt)

# Global variable to store orders (in a real app, this would be a database)
all_orders = []

def _load_orders_from_db():
    global all_orders
    try:
        if cursor:
            cursor.execute("SELECT order_id, user_email, user_name, phone, address, postal, city, date, items, total, payment_method, payment_id, status FROM orders")
            rows = cursor.fetchall()
            loaded = []
            for r in rows:
                loaded.append({
                    'order_id': r['order_id'],
                    'user_email': r['user_email'],
                    'user_name': r['user_name'],
                    'phone': r['phone'],
                    'address': r['address'],
                    'postal': r['postal'],
                    'city': r['city'],
                    'date': r['date'].strftime('%Y-%m-%d %H:%M:%S') if hasattr(r['date'], 'strftime') else str(r['date']),
                    'processing_start': datetime.datetime.strptime(r['date'], '%Y-%m-%d %H:%M:%S') if isinstance(r['date'], str) else r['date'],
                    'items': r['items'].split(',') if r['items'] else [],
                    'total': float(r['total']),
                    'payment_method': r['payment_method'],
                    'payment_id': r['payment_id'],
                    'status': r['status']
                })
            all_orders = loaded
            print(f'Loaded {len(all_orders)} orders from database')
        else:
            print('DB cursor not available; orders list is empty')
            all_orders = []
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
    return render_template('admin_dashboard.html', users=users, total_users=total_users, total_orders=total_orders, total_revenue=total_revenue, all_orders=all_orders, orders_per_user=orders_per_user)

@app.route('/api/orders')
def api_orders():
    user_email = session.get('user')
    if not user_email:
        return {'error': 'Not logged in'}, 401
    user = next((u for u in users if u['email'] == user_email), None)
    if not user or user.get('role') != 'admin':
        return {'error': 'Unauthorized'}, 403
    total_revenue = sum(order['total'] for order in all_orders)
    return {'orders': all_orders, 'total_users': len(users), 'total_orders': len(all_orders), 'total_revenue': total_revenue}

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
            if cursor:
                cursor.execute("UPDATE orders SET status = 'Cancelled' WHERE order_id = %s", (order_id,))
                conn.commit()
        except Exception as e:
            print('Error updating order status in database:', e)

        # Real time updates
        socketio.emit('order_update', {'order_id': order_id, 'status': 'Cancelled', 'user_email': order['user_email']})
        return {'success': True}
    return {'error': 'Invalid order ID or status'}, 400

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
            if cursor:
                cursor.execute("UPDATE orders SET status = 'Paid' WHERE order_id = %s", (order_id,))
                conn.commit()
        except Exception as e:
            print('Error updating order status in database:', e)
        # Emit real-time updates
        socketio.emit('order_update', {'order_id': order_id, 'status': 'Paid', 'user_email': order['user_email']})
        return {'success': True}
    return {'error': 'Invalid order ID or status'}, 400

@socketio.on('connect')
def handle_connect():
    user_email = session.get('user')
    if user_email:
        join_room(user_email)
        user = next((u for u in users if u['email'] == user_email), None)
        if user and user.get('role') == 'admin':
            join_room('admin')
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

if __name__ == '__main__':
    socketio.run(app, debug=True)
