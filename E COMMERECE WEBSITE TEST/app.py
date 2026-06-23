import random
import re
import os
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage
from functools import wraps
from flask import Flask, render_template, redirect, url_for, request, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, UserMixin, login_user, login_required, current_user, logout_user
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import generate_password_hash, check_password_hash
import stripe
import json

try:
    from twilio.rest import Client as TwilioClient
except Exception:
    TwilioClient = None

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-this-secret-key")

# Database configuration
DATABASE_URL = os.environ.get("DATABASE_URL") or f"sqlite:///{os.path.join(os.path.dirname(__file__), 'ecommerce.db')}"
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Rate limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# Login manager
login_manager = LoginManager(app)
login_manager.login_view = 'login'


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(255), nullable=True)
    is_admin = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id):
    try:
        return User.query.get(int(user_id))
    except Exception:
        return None


@app.context_processor
def inject_user():
    cart = session.get('cart', {})
    cart_count = sum(cart.values())
    categories = Category.query.order_by(Category.name).all() if db.session else []
    return dict(current_user=current_user, cart_count=cart_count, categories=categories)


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    products = db.relationship('Product', backref='category', lazy=True)

    def __repr__(self):
        return f"<Category {self.name}>"


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(255), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    image_url = db.Column(db.String(500), nullable=True)
    inventory = db.Column(db.Integer, default=100)
    active = db.Column(db.Boolean, default=True)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviews = db.relationship('ProductReview', backref='product', lazy=True)

    def __repr__(self):
        return f"<Product {self.name}>"


class ProductReview(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=False)
    approved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Review {self.rating} for {self.product_id}>"


class Coupon(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    discount_percent = db.Column(db.Integer, nullable=True)
    discount_amount = db.Column(db.Numeric(10, 2), nullable=True)
    active = db.Column(db.Boolean, default=True)
    expires_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f"<Coupon {self.code}>"


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    status = db.Column(db.String(50), default='pending')
    payment_status = db.Column(db.String(50), default='unpaid')
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    shipping_address = db.Column(db.Text, nullable=True)
    phone = db.Column(db.String(80), nullable=True)
    email = db.Column(db.String(255), nullable=False)
    coupon_id = db.Column(db.Integer, db.ForeignKey('coupon.id'), nullable=True)
    shipping_method_id = db.Column(db.Integer, db.ForeignKey('shipping_method.id'), nullable=True)
    shipping_cost = db.Column(db.Numeric(10, 2), default=0)
    tracking_number = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    items = db.relationship('OrderItem', backref='order', lazy=True)
    coupon = db.relationship('Coupon', backref='orders')
    shipping_method = db.relationship('ShippingMethod', backref='orders')

    def __repr__(self):
        return f"<Order {self.id}>"


class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price_at_purchase = db.Column(db.Numeric(10, 2), nullable=False)
    product = db.relationship('Product', backref='order_items')

    def __repr__(self):
        return f"<OrderItem {self.product_id} x {self.quantity}>"


class ShippingMethod(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    cost = db.Column(db.Numeric(10, 2), nullable=False)
    delivery_days = db.Column(db.Integer, default=3)
    active = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f"<ShippingMethod {self.name}>"


class UserActivity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    action = db.Column(db.String(50), nullable=False)  # view, cart, purchase, review
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Activity {self.action}>"


class Analytics(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    metric_date = db.Column(db.Date, default=datetime.utcnow().date())
    total_views = db.Column(db.Integer, default=0)
    total_purchases = db.Column(db.Integer, default=0)
    total_revenue = db.Column(db.Numeric(10, 2), default=0)
    top_product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=True)
    conversion_rate = db.Column(db.Numeric(5, 2), default=0)

    def __repr__(self):
        return f"<Analytics {self.metric_date}>"


def admin_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Admin access required.')
            return redirect(url_for('login'))
        return view_func(*args, **kwargs)
    return wrapped


def get_cart():
    return session.get('cart', {})


def save_cart(cart):
    session["cart"] = cart


def send_email_otp(to_email: str, otp: str) -> bool:
    host = os.environ.get("SMTP_HOST")
    port = os.environ.get("SMTP_PORT")
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASS")
    if not (host and port and user and password):
        return False
    try:
        msg = EmailMessage()
        msg["Subject"] = "Your Al Amoodi Enterprises OTP Code"
        msg["From"] = user
        msg["To"] = to_email
        msg.set_content(f"Your OTP code is: {otp}")

        port_int = int(port)
        if port_int == 465:
            server = smtplib.SMTP_SSL(host, port_int, timeout=10)
        else:
            server = smtplib.SMTP(host, port_int, timeout=10)
            server.starttls()

        server.login(user, password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception:
        return False


def send_sms_otp(phone: str, otp: str) -> bool:
    sid = os.environ.get("TWILIO_ACCOUNT_SID")
    token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_number = os.environ.get("TWILIO_FROM_NUMBER")
    if not (sid and token and from_number and TwilioClient):
        return False
    try:
        client = TwilioClient(sid, token)
        client.messages.create(body=f"Your Al Amoodi OTP: {otp}", from_=from_number, to=phone)
        return True
    except Exception:
        return False


def send_order_confirmation(order):
    """Send order confirmation email with order details and tracking info"""
    host = os.environ.get("SMTP_HOST")
    port = os.environ.get("SMTP_PORT")
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASS")
    if not (host and port and user and password):
        return False
    try:
        items_html = ""
        for item in order.items:
            items_html += f"<li>{item.product.name} x{item.quantity} = ${float(item.price_at_purchase) * item.quantity:.2f}</li>"
        
        body = f"""
        <h2>Order Confirmation</h2>
        <p>Thank you for your order! Order #{order.id}</p>
        <h3>Items:</h3>
        <ul>{items_html}</ul>
        <p><strong>Total: ${float(order.total_amount):.2f}</strong></p>
        <p>Shipping: {order.shipping_method.name if order.shipping_method else 'Standard'}</p>
        <p>Status: {order.status}</p>
        {f'Tracking: {order.tracking_number}' if order.tracking_number else ''}
        """
        
        msg = EmailMessage()
        msg['Subject'] = f'Order Confirmation #{order.id} - Al Amoodi Enterprises'
        msg['From'] = user
        msg['To'] = order.email
        msg.set_content(body, subtype='html')
        
        port_int = int(port)
        if port_int == 465:
            server = smtplib.SMTP_SSL(host, port_int, timeout=10)
        else:
            server = smtplib.SMTP(host, port_int, timeout=10)
            server.starttls()
        
        server.login(user, password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception:
        return False


def get_related_products(product_id, limit=4):
    """Get related products in same category"""
    product = Product.query.get(product_id)
    if not product or not product.category_id:
        return []
    return Product.query.filter(
        Product.category_id == product.category_id,
        Product.id != product_id,
        Product.active == True
    ).limit(limit).all()


def decrement_inventory(product_id, quantity):
    """Decrement product inventory and check for low stock"""
    product = Product.query.get(product_id)
    if product:
        product.inventory -= quantity
        if product.inventory < 0:
            product.inventory = 0
        db.session.commit()
        return product.inventory
    return None


def log_user_activity(action, product_id=None):
    """Log user activity for analytics"""
    try:
        activity = UserActivity(
            user_id=current_user.id if current_user.is_authenticated else None,
            action=action,
            product_id=product_id
        )
        db.session.add(activity)
        db.session.commit()
    except Exception:
        pass


def update_daily_analytics():
    """Update daily analytics metrics"""
    try:
        today = datetime.utcnow().date()
        analytics = Analytics.query.filter_by(metric_date=today).first()
        if not analytics:
            analytics = Analytics(metric_date=today)
            db.session.add(analytics)
        
        analytics.total_views = UserActivity.query.filter_by(action='view').filter(
            UserActivity.created_at >= datetime.utcnow() - timedelta(days=1)
        ).count()
        
        analytics.total_purchases = Order.query.filter(
            Order.created_at >= datetime.utcnow() - timedelta(days=1)
        ).count()
        
        analytics.total_revenue = db.session.query(db.func.sum(Order.total_amount)).filter(
            Order.created_at >= datetime.utcnow() - timedelta(days=1)
        ).scalar() or 0
        
        db.session.commit()
    except Exception:
        pass


@app.route("/")
def index():
    q = request.args.get('q', '').strip()
    sort_by = request.args.get('sort', 'newest')
    category_id = request.args.get('category')
    
    query = Product.query.filter_by(active=True)
    
    if category_id:
        query = query.filter_by(category_id=int(category_id))
    
    if q:
        query = query.filter((Product.name.ilike(f'%{q}%')) | (Product.description.ilike(f'%{q}%')))
    
    if sort_by == 'price_low':
        query = query.order_by(Product.price.asc())
    elif sort_by == 'price_high':
        query = query.order_by(Product.price.desc())
    else:
        query = query.order_by(Product.created_at.desc())
    
    products = query.all()
    return render_template("index.html", products=products, query=q)


@app.route("/product/<int:product_id>")
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    reviews = ProductReview.query.filter_by(product_id=product_id, approved=True).all()
    related_products = get_related_products(product_id)
    avg_rating = 0
    if reviews:
        avg_rating = sum(r.rating for r in reviews) / len(reviews)
    log_user_activity('view', product_id)
    return render_template('product.html', product=product, reviews=reviews, avg_rating=avg_rating, related_products=related_products)


@app.route("/add-to-cart/<int:product_id>")
def add_to_cart(product_id):
    cart = get_cart()
    cart[str(product_id)] = cart.get(str(product_id), 0) + 1
    save_cart(cart)
    flash("Added to cart.")
    return redirect(url_for("index"))


@app.route("/remove-from-cart/<int:product_id>")
def remove_from_cart(product_id):
    cart = get_cart()
    key = str(product_id)
    if key in cart:
        cart.pop(key)
        save_cart(cart)
        flash("Removed item from cart.")
    return redirect(url_for("cart"))


@app.route("/cart")
def cart():
    cart = get_cart()
    cart_items = []
    total = 0.0
    for pid, quantity in cart.items():
        product = Product.query.get(int(pid))
        if product and product.inventory > 0:
            subtotal = float(product.price) * quantity
            total += subtotal
            cart_items.append({"product": product, "quantity": quantity, "subtotal": subtotal})
    return render_template("cart.html", cart_items=cart_items, total=total)


@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    cart = get_cart()
    if not cart:
        flash("Your cart is empty.")
        return redirect(url_for("index"))

    otp_required = bool(session.get("checkout_otp"))
    step = request.args.get('step', '1')
    shipping_methods = ShippingMethod.query.filter_by(active=True).all()

    if request.method == "POST":
        if request.form.get("otp") is not None:
            otp = request.form.get("otp", "").strip()
            saved_otp = session.get("checkout_otp")
            if not saved_otp or otp != saved_otp:
                flash("OTP is incorrect. Please try again.")
                otp_required = True
            else:
                checkout_info = session.pop("checkout_info", {})
                session.pop("checkout_otp", None)
                # Redirect to Stripe checkout
                return redirect(url_for('checkout_stripe'))
        else:
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip()
            email_confirm = request.form.get("email_confirm", "").strip()
            phone = request.form.get("phone", "").strip()
            phone_confirm = request.form.get("phone_confirm", "").strip()

            if not name or not email or not email_confirm or not phone or not phone_confirm:
                flash("Please complete all checkout fields.")
                return redirect(url_for("checkout"))

            if email != email_confirm:
                flash("Email and confirmation email do not match.")
                return redirect(url_for("checkout"))

            if phone != phone_confirm:
                flash("Phone number and confirmation phone number do not match.")
                return redirect(url_for("checkout"))

            email_pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
            phone_pattern = r"^[0-9()+\-\s]{7,20}$"

            if not re.match(email_pattern, email):
                flash("Please enter a valid email address.")
                return redirect(url_for("checkout"))

            if not re.match(phone_pattern, phone):
                flash("Please enter a valid phone number.")
                return redirect(url_for("checkout"))

            otp = f"{random.randint(100000, 999999)}"
            session["checkout_info"] = {"name": name, "email": email, "phone": phone}
            session["checkout_otp"] = otp

            email_sent = send_email_otp(email, otp)
            sms_sent = send_sms_otp(phone, otp)

            if email_sent or sms_sent:
                flash("OTP sent to your contact methods. Please enter it to complete the order.")
            else:
                flash(f"OTP code sent (demo): {otp}")

            otp_required = True

    cart_items = []
    total = 0.0
    for pid, quantity in cart.items():
        product = Product.query.get(int(pid))
        if product:
            subtotal = float(product.price) * quantity
            total += subtotal
            cart_items.append({"product": product, "quantity": quantity, "subtotal": subtotal})

    return render_template("checkout.html", cart_items=cart_items, total=total, otp_required=otp_required, shipping_methods=shipping_methods, step=step)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        if not email or not password:
            flash('Email and password are required.')
            return redirect(url_for('register'))
        if User.query.filter_by(email=email).first():
            flash('Account with that email already exists.')
            return redirect(url_for('register'))
        user = User(email=email, name=name)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash('Account created and logged in.')
        return redirect(url_for('index'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            flash('Logged in successfully.')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        flash('Invalid credentials.')
        return redirect(url_for('login'))
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out.')
    return redirect(url_for('index'))


# ===== ADMIN DASHBOARD =====
@app.route('/admin')
@admin_required
def admin_dashboard():
    total_orders = Order.query.count()
    total_revenue = db.session.query(db.func.sum(Order.total_amount)).scalar() or 0
    total_products = Product.query.count()
    total_users = User.query.count()
    low_stock_products = Product.query.filter(Product.inventory < 10).all()
    return render_template('admin/dashboard.html', total_orders=total_orders, total_revenue=total_revenue, total_products=total_products, total_users=total_users, low_stock_products=low_stock_products)


@app.route('/admin/products', methods=['GET', 'POST'])
@admin_required
def admin_products():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        slug = request.form.get('slug', '').strip()
        description = request.form.get('description', '').strip()
        price = request.form.get('price', '0')
        inventory = request.form.get('inventory', '0')
        category_id = request.form.get('category_id')
        
        product = Product(name=name, slug=slug, description=description, price=float(price), inventory=int(inventory), category_id=int(category_id) if category_id else None)
        db.session.add(product)
        db.session.commit()
        flash('Product created successfully.')
        return redirect(url_for('admin_products'))
    
    products = Product.query.all()
    categories = Category.query.all()
    return render_template('admin/products.html', products=products, categories=categories)


@app.route('/admin/products/<int:product_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    if request.method == 'POST':
        product.name = request.form.get('name', '').strip()
        product.slug = request.form.get('slug', '').strip()
        product.description = request.form.get('description', '').strip()
        product.price = float(request.form.get('price', '0'))
        product.inventory = int(request.form.get('inventory', '0'))
        category_id = request.form.get('category_id')
        product.category_id = int(category_id) if category_id else None
        db.session.commit()
        flash('Product updated successfully.')
        return redirect(url_for('admin_products'))
    
    categories = Category.query.all()
    return render_template('admin/edit_product.html', product=product, categories=categories)


@app.route('/admin/products/<int:product_id>/delete', methods=['POST'])
@admin_required
def admin_delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()
    flash('Product deleted.')
    return redirect(url_for('admin_products'))


@app.route('/admin/orders')
@admin_required
def admin_orders():
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template('admin/orders.html', orders=orders)


@app.route('/admin/reviews')
@admin_required
def admin_reviews():
    reviews = ProductReview.query.filter_by(approved=False).all()
    return render_template('admin/reviews.html', reviews=reviews)


@app.route('/admin/review/<int:review_id>/approve', methods=['POST'])
@admin_required
def admin_approve_review(review_id):
    review = ProductReview.query.get_or_404(review_id)
    review.approved = True
    db.session.commit()
    flash('Review approved.')
    return redirect(url_for('admin_reviews'))


@app.route('/admin/coupons', methods=['GET', 'POST'])
@admin_required
def admin_coupons():
    if request.method == 'POST':
        code = request.form.get('code', '').strip().upper()
        discount_percent = request.form.get('discount_percent', '')
        discount_amount = request.form.get('discount_amount', '')
        
        coupon = Coupon(code=code, discount_percent=int(discount_percent) if discount_percent else None, discount_amount=float(discount_amount) if discount_amount else None, active=True)
        db.session.add(coupon)
        db.session.commit()
        flash('Coupon created.')
        return redirect(url_for('admin_coupons'))
    
    coupons = Coupon.query.all()
    return render_template('admin/coupons.html', coupons=coupons)


# ===== SHIPPING MANAGEMENT =====
@app.route('/admin/shipping', methods=['GET', 'POST'])
@admin_required
def admin_shipping():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        cost = request.form.get('cost', '0')
        delivery_days = request.form.get('delivery_days', '3')
        
        method = ShippingMethod(name=name, cost=float(cost), delivery_days=int(delivery_days), active=True)
        db.session.add(method)
        db.session.commit()
        flash('Shipping method added.')
        return redirect(url_for('admin_shipping'))
    
    methods = ShippingMethod.query.filter_by(active=True).all()
    return render_template('admin/shipping.html', methods=methods)


# ===== ANALYTICS =====
@app.route('/admin/analytics')
@admin_required
def admin_analytics():
    update_daily_analytics()
    analytics = Analytics.query.order_by(Analytics.metric_date.desc()).limit(30).all()
    total_revenue_all_time = db.session.query(db.func.sum(Order.total_amount)).scalar() or 0
    total_orders_all_time = Order.query.count()
    return render_template('admin/analytics.html', analytics=analytics, total_revenue=total_revenue_all_time, total_orders=total_orders_all_time)


# ===== API ENDPOINTS =====
@app.route('/api/related-products/<int:product_id>')
@limiter.limit("30 per minute")
def api_related_products(product_id):
    related = get_related_products(product_id, limit=6)
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'price': float(p.price),
        'image_url': p.image_url or '/static/images/placeholder.svg'
    } for p in related])


# ===== USER ORDERS & HISTORY =====
@app.route('/orders')
@login_required
def user_orders():
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template('orders.html', orders=orders)


@app.route('/orders/<int:order_id>')
@login_required
def order_detail(order_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id != current_user.id and not current_user.is_admin:
        flash('Unauthorized.')
        return redirect(url_for('user_orders'))
    return render_template('order_detail.html', order=order)


# ===== REVIEWS =====
@app.route('/product/<int:product_id>/review', methods=['POST'])
@login_required
def add_review(product_id):
    product = Product.query.get_or_404(product_id)
    rating = request.form.get('rating', '5')
    comment = request.form.get('comment', '').strip()
    
    review = ProductReview(user_id=current_user.id, product_id=product_id, rating=int(rating), comment=comment, approved=False)
    db.session.add(review)
    db.session.commit()
    flash('Review submitted for moderation.')
    return redirect(url_for('product_detail', product_id=product_id))


# ===== STRIPE CHECKOUT =====
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY', 'sk_test_placeholder')


@app.route('/checkout-stripe', methods=['GET', 'POST'])
def checkout_stripe():
    cart = get_cart()
    if not cart:
        flash('Your cart is empty.')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        cart_items = []
        total = 0.0
        for pid, quantity in cart.items():
            product = Product.query.get(int(pid))
            if product:
                subtotal = float(product.price) * quantity
                total += subtotal
                cart_items.append({'product': product, 'quantity': quantity, 'subtotal': subtotal})
        
        # Create Stripe checkout session
        line_items = []
        for item in cart_items:
            line_items.append({
                'price_data': {
                    'currency': 'usd',
                    'product_data': {'name': item['product'].name},
                    'unit_amount': int(item['product'].price * 100),
                },
                'quantity': item['quantity'],
            })
        
        try:
            session_obj = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=line_items,
                mode='payment',
                success_url=url_for('checkout_success', _external=True),
                cancel_url=url_for('checkout_stripe', _external=True),
            )
            return redirect(session_obj.url, code=303)
        except Exception as e:
            flash(f'Payment error: {str(e)}')
            return redirect(url_for('checkout_stripe'))
    
    cart_items = []
    total = 0.0
    for pid, quantity in cart.items():
        product = Product.query.get(int(pid))
        if product:
            subtotal = float(product.price) * quantity
            total += subtotal
            cart_items.append({'product': product, 'quantity': quantity, 'subtotal': subtotal})
    
    return render_template('checkout_stripe.html', cart_items=cart_items, total=total)


@app.route('/checkout-success')
def checkout_success():
    cart = get_cart()
    if not cart:
        return redirect(url_for('index'))
    
    email = request.args.get('email', current_user.email if current_user.is_authenticated else 'guest@example.com')
    shipping_method_id = request.args.get('shipping_method_id')
    shipping_method = ShippingMethod.query.get(shipping_method_id) if shipping_method_id else None
    shipping_cost = float(shipping_method.cost) if shipping_method else 0
    
    order = Order(user_id=current_user.id if current_user.is_authenticated else None, email=email, total_amount=0, status='pending', payment_status='paid', shipping_method_id=shipping_method_id, shipping_cost=shipping_cost)
    
    total = 0.0
    for pid, quantity in cart.items():
        product = Product.query.get(int(pid))
        if product:
            price = float(product.price)
            total += price * quantity
            item = OrderItem(order=order, product_id=product.id, quantity=quantity, price_at_purchase=price)
            order.items.append(item)
            # Decrement inventory
            decrement_inventory(product.id, quantity)
            log_user_activity('purchase', product.id)
    
    total += shipping_cost
    order.total_amount = total
    order.tracking_number = f"AAE{order.id}{datetime.utcnow().strftime('%Y%m%d')}"
    db.session.add(order)
    db.session.commit()
    
    # Send order confirmation email
    send_order_confirmation(order)
    
    session.pop('cart', None)
    flash('Order placed successfully!')
    return render_template('thankyou.html', name=email, order_id=order.id)



if __name__ == "__main__":
    # create DB tables if missing (dev only)
    with app.app_context():
        try:
            db.create_all()
        except Exception:
            pass
    app.run(debug=True)
