"""
Seed script to populate database with initial data for development/testing
Run with: python seed_data.py
"""
import os
import sys
from datetime import datetime, timedelta
from app import app, db, User, Product, Category, Coupon, ShippingMethod, Order, OrderItem

def seed_database():
    """Populate database with sample data"""
    
    with app.app_context():
        # Clear existing data (dev only)
        print("🗑️  Clearing existing data...")
        db.session.query(OrderItem).delete()
        db.session.query(Order).delete()
        db.session.query(Product).delete()
        db.session.query(Category).delete()
        db.session.query(User).delete()
        db.session.query(Coupon).delete()
        db.session.query(ShippingMethod).delete()
        db.session.commit()
        
        # Create users
        print("👥 Creating users...")
        admin = User(
            email='admin@amoodi.com',
            name='Admin User',
            is_admin=True
        )
        admin.set_password('admin123')
        
        customer1 = User(
            email='customer1@example.com',
            name='Ahmed Hassan',
            is_admin=False
        )
        customer1.set_password('password123')
        
        customer2 = User(
            email='customer2@example.com',
            name='Fatima Ali',
            is_admin=False
        )
        customer2.set_password('password123')
        
        db.session.add_all([admin, customer1, customer2])
        db.session.commit()
        print(f"✅ Created {User.query.count()} users")
        
        # Create categories
        print("📂 Creating categories...")
        categories_data = [
            {'name': 'Electronics', 'slug': 'electronics', 'description': 'Gadgets and electronic devices'},
            {'name': 'Clothing', 'slug': 'clothing', 'description': 'Fashion and apparel'},
            {'name': 'Home & Garden', 'slug': 'home-garden', 'description': 'Home and garden products'},
            {'name': 'Sports', 'slug': 'sports', 'description': 'Sports and fitness equipment'},
            {'name': 'Books', 'slug': 'books', 'description': 'Books and educational materials'},
        ]
        
        categories = []
        for cat_data in categories_data:
            category = Category(**cat_data)
            db.session.add(category)
            categories.append(category)
        db.session.commit()
        print(f"✅ Created {Category.query.count()} categories")
        
        # Create products
        print("🛍️  Creating products...")
        products_data = [\n            # Electronics
            {'name': 'Wireless Headphones', 'slug': 'wireless-headphones', 'category_id': categories[0].id, 'price': 79.99, 'inventory': 50, 'description': 'High-quality wireless headphones with noise cancellation'},
            {'name': 'USB-C Cable', 'slug': 'usb-c-cable', 'category_id': categories[0].id, 'price': 12.99, 'inventory': 200, 'description': 'Durable 6ft USB-C charging and data cable'},
            {'name': 'Phone Stand', 'slug': 'phone-stand', 'category_id': categories[0].id, 'price': 24.99, 'inventory': 100, 'description': 'Adjustable phone stand for desk or table'},
            {'name': 'Power Bank', 'slug': 'power-bank', 'category_id': categories[0].id, 'price': 34.99, 'inventory': 75, 'description': '20000mAh portable power bank with fast charging'},
            
            # Clothing
            {'name': 'Cotton T-Shirt', 'slug': 'cotton-tshirt', 'category_id': categories[1].id, 'price': 19.99, 'inventory': 300, 'description': '100% organic cotton comfortable t-shirt'},
            {'name': 'Denim Jeans', 'slug': 'denim-jeans', 'category_id': categories[1].id, 'price': 59.99, 'inventory': 150, 'description': 'Classic blue denim jeans for everyday wear'},
            {'name': 'Sports Cap', 'slug': 'sports-cap', 'category_id': categories[1].id, 'price': 16.99, 'inventory': 120, 'description': 'Lightweight sports cap with adjustable strap'},
            
            # Home & Garden
            {'name': 'LED Desk Lamp', 'slug': 'led-desk-lamp', 'category_id': categories[2].id, 'price': 39.99, 'inventory': 60, 'description': 'Adjustable LED lamp with touch control and USB charging'},
            {'name': 'Coffee Maker', 'slug': 'coffee-maker', 'category_id': categories[2].id, 'price': 89.99, 'inventory': 40, 'description': 'Automatic coffee maker with 12-cup capacity'},
            {'name': 'Plant Pot', 'slug': 'plant-pot', 'category_id': categories[2].id, 'price': 14.99, 'inventory': 150, 'description': 'Ceramic plant pot with drainage hole'},
            
            # Sports
            {'name': 'Yoga Mat', 'slug': 'yoga-mat', 'category_id': categories[3].id, 'price': 29.99, 'inventory': 80, 'description': 'Non-slip yoga mat 6mm thickness'},
            {'name': 'Dumbbells Set', 'slug': 'dumbbells', 'category_id': categories[3].id, 'price': 49.99, 'inventory': 45, 'description': '20kg adjustable dumbbell set'},
            {'name': 'Running Shoes', 'slug': 'running-shoes', 'category_id': categories[3].id, 'price': 99.99, 'inventory': 85, 'description': 'Professional running shoes with cushioning'},
            
            # Books
            {'name': 'Python Programming', 'slug': 'python-book', 'category_id': categories[4].id, 'price': 39.99, 'inventory': 100, 'description': 'Complete guide to Python programming'},
            {'name': 'Web Design Guide', 'slug': 'web-design', 'category_id': categories[4].id, 'price': 34.99, 'inventory': 70, 'description': 'Modern web design principles and practices'},
        ]
        
        products = []
        for prod_data in products_data:
            product = Product(
                name=prod_data['name'],
                slug=prod_data['slug'],
                category_id=prod_data['category_id'],
                price=prod_data['price'],
                inventory=prod_data['inventory'],
                description=prod_data['description'],
                active=True
            )
            db.session.add(product)
            products.append(product)
        db.session.commit()
        print(f"✅ Created {Product.query.count()} products")
        
        # Create shipping methods
        print("🚚 Creating shipping methods...")
        shipping_methods = [
            ShippingMethod(name='Standard Shipping', cost=5.99, delivery_days=5),
            ShippingMethod(name='Express Shipping', cost=14.99, delivery_days=2),
            ShippingMethod(name='Overnight Shipping', cost=24.99, delivery_days=1),
            ShippingMethod(name='Free Shipping (7-10 days)', cost=0, delivery_days=10),
        ]
        db.session.add_all(shipping_methods)
        db.session.commit()
        print(f"✅ Created {ShippingMethod.query.count()} shipping methods")
        
        # Create coupons
        print("🎟️  Creating coupons...")
        coupons = [
            Coupon(code='WELCOME10', discount_percent=10, active=True),
            Coupon(code='SAVE20', discount_percent=20, active=True),
            Coupon(code='FREESHIP', discount_amount=5.99, active=True),
            Coupon(code='EXPIRED', discount_percent=50, active=False, expires_at=datetime.utcnow() - timedelta(days=1)),
        ]
        db.session.add_all(coupons)
        db.session.commit()
        print(f"✅ Created {Coupon.query.count()} coupons")
        
        # Create sample orders
        print("📦 Creating sample orders...")
        order1 = Order(
            user_id=customer1.id,
            email=customer1.email,
            status='completed',
            payment_status='paid',
            total_amount=99.99,
            shipping_address='123 Main St, Cairo, Egypt',
            phone='+201234567890',
            shipping_method_id=shipping_methods[0].id,
            shipping_cost=5.99,
            tracking_number=f'AAE{1}{datetime.utcnow().strftime(\"%Y%m%d\")}'
        )
        
        # Add items to order
        item1 = OrderItem(
            order=order1,
            product_id=products[0].id,
            quantity=2,
            price_at_purchase=79.99
        )
        
        db.session.add_all([order1, item1])
        db.session.commit()
        print(f"✅ Created {Order.query.count()} orders")
        
        # Summary
        print("\n" + "="*50)
        print("✅ DATABASE SEEDING COMPLETED!")
        print("="*50)
        print(f"Users: {User.query.count()}")
        print(f"Categories: {Category.query.count()}")
        print(f"Products: {Product.query.count()}")
        print(f"Shipping Methods: {ShippingMethod.query.count()}")
        print(f"Coupons: {Coupon.query.count()}")
        print(f"Orders: {Order.query.count()}")
        print("\n📌 Test Credentials:")
        print("Admin: admin@amoodi.com / admin123")
        print("Customer: customer1@example.com / password123")
        print("="*50)


if __name__ == '__main__':
    try:
        seed_database()
    except Exception as e:
        print(f"❌ Error seeding database: {e}")
        sys.exit(1)
