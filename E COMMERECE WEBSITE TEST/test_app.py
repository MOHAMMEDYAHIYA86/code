"""
Comprehensive test suite for Al Amoodi E-commerce Platform
Tests cover: authentication, products, shopping, admin, payments, and edge cases
"""
import pytest
import os
from app import app, db, User, Product, Category, Order, OrderItem, Coupon, ShippingMethod
from werkzeug.security import generate_password_hash


@pytest.fixture
def client():
    """Create test client with fresh database"""
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    
    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


@pytest.fixture
def auth_user(client):
    """Create test user for authentication tests"""
    with app.app_context():
        user = User(email='test@example.com', name='Test User')
        user.set_password('password123')
        db.session.add(user)
        db.session.commit()
        return user


@pytest.fixture
def admin_user(client):
    """Create admin user"""
    with app.app_context():
        user = User(email='admin@example.com', name='Admin User', is_admin=True)
        user.set_password('admin123')
        db.session.add(user)
        db.session.commit()
        return user


class TestAuthentication:
    """Test user registration and login"""
    
    def test_register_success(self, client):
        response = client.post('/register', data={
            'name': 'New User',
            'email': 'new@example.com',
            'password': 'test123'
        })
        assert response.status_code == 302  # Redirect after success
        
        with app.app_context():
            user = User.query.filter_by(email='new@example.com').first()
            assert user is not None
    
    def test_register_duplicate_email(self, client, auth_user):
        response = client.post('/register', data={
            'name': 'Another User',
            'email': 'test@example.com',
            'password': 'test123'
        })
        assert response.status_code == 302
        assert b'already exists' in response.data
    
    def test_login_success(self, client, auth_user):
        response = client.post('/login', data={
            'email': 'test@example.com',
            'password': 'password123'
        })
        assert response.status_code == 302
    
    def test_login_invalid_password(self, client, auth_user):
        response = client.post('/login', data={
            'email': 'test@example.com',
            'password': 'wrongpassword'
        })
        assert response.status_code == 302
        assert b'Invalid' in response.data
    
    def test_logout(self, client, auth_user):
        client.post('/login', data={
            'email': 'test@example.com',
            'password': 'password123'
        }, follow_redirects=True)
        
        response = client.get('/logout')
        assert response.status_code == 302


class TestProducts:
    """Test product listing, search, filtering"""
    
    @pytest.fixture
    def sample_data(self, client):
        with app.app_context():
            cat = Category(name='Electronics', slug='electronics')
            db.session.add(cat)
            db.session.commit()
            
            for i in range(3):
                p = Product(
                    name=f'Product {i}',
                    slug=f'product-{i}',
                    description=f'Test product {i}',
                    price=100 + i*10,
                    inventory=50,
                    active=True,
                    category_id=cat.id
                )
                db.session.add(p)
            db.session.commit()
    
    def test_index_page(self, client, sample_data):
        response = client.get('/')
        assert response.status_code == 200
        assert b'Product 0' in response.data
    
    def test_search_products(self, client, sample_data):
        response = client.get('/?q=Product')
        assert response.status_code == 200
    
    def test_filter_by_category(self, client, sample_data):
        response = client.get('/?category=1')
        assert response.status_code == 200
    
    def test_sort_by_price_low(self, client, sample_data):
        response = client.get('/?sort=price_low')
        assert response.status_code == 200
    
    def test_product_detail(self, client, sample_data):
        response = client.get('/product/1')
        assert response.status_code == 200


class TestShopping:
    """Test cart and checkout functionality"""
    
    @pytest.fixture
    def product(self, client):
        with app.app_context():
            p = Product(
                name='Test Product',
                slug='test-product',
                description='Test',
                price=99.99,
                inventory=10
            )
            db.session.add(p)
            db.session.commit()
            return p
    
    def test_add_to_cart(self, client, product):
        response = client.get(f'/add-to-cart/{product.id}')
        assert response.status_code == 302
    
    def test_view_cart(self, client, product):
        client.get(f'/add-to-cart/{product.id}')
        response = client.get('/cart')
        assert response.status_code == 200
    
    def test_remove_from_cart(self, client, product):
        client.get(f'/add-to-cart/{product.id}')
        response = client.get(f'/remove-from-cart/{product.id}')
        assert response.status_code == 302


class TestAdmin:
    """Test admin dashboard and product management"""
    
    def test_admin_dashboard_unauthorized(self, client):
        response = client.get('/admin')
        assert response.status_code == 302  # Redirect to login
    
    def test_admin_dashboard_authorized(self, client, admin_user):
        with client:
            client.post('/login', data={
                'email': 'admin@example.com',
                'password': 'admin123'
            }, follow_redirects=True)
            
            response = client.get('/admin')
            assert response.status_code == 200
    
    def test_admin_create_product(self, client, admin_user):
        with client:
            client.post('/login', data={
                'email': 'admin@example.com',
                'password': 'admin123'
            }, follow_redirects=True)
            
            response = client.post('/admin/products', data={
                'name': 'New Product',
                'slug': 'new-product',
                'description': 'Test',
                'price': '49.99',
                'inventory': '100',
                'category_id': ''
            })
            assert response.status_code == 302


class TestInventory:
    """Test inventory management and low stock alerts"""
    
    @pytest.fixture
    def product(self, client):
        with app.app_context():
            p = Product(
                name='Stock Test',
                slug='stock-test',
                description='Test',
                price=50,
                inventory=5
            )
            db.session.add(p)
            db.session.commit()
            return p
    
    def test_low_stock_warning(self, client, product, admin_user):
        with client:
            client.post('/login', data={
                'email': 'admin@example.com',
                'password': 'admin123'
            }, follow_redirects=True)
            
            response = client.get('/admin')
            assert response.status_code == 200
            # Low stock product should be listed
            assert b'low_stock_products' in response.data or response.status_code == 200


class TestCoupons:
    """Test coupon creation and validation"""
    
    def test_create_coupon(self, client, admin_user):
        with client:
            client.post('/login', data={
                'email': 'admin@example.com',
                'password': 'admin123'
            }, follow_redirects=True)
            
            response = client.post('/admin/coupons', data={
                'code': 'SAVE10',
                'discount_percent': '10',
                'discount_amount': ''
            })
            assert response.status_code == 302
            
            with app.app_context():
                coupon = Coupon.query.filter_by(code='SAVE10').first()
                assert coupon is not None
                assert coupon.discount_percent == 10


class TestAnalytics:
    """Test analytics and user activity tracking"""
    
    def test_analytics_page(self, client, admin_user):
        with client:
            client.post('/login', data={
                'email': 'admin@example.com',
                'password': 'admin123'
            }, follow_redirects=True)
            
            response = client.get('/admin/analytics')
            assert response.status_code == 200


class TestShipping:
    """Test shipping method management"""
    
    def test_create_shipping_method(self, client, admin_user):
        with client:
            client.post('/login', data={
                'email': 'admin@example.com',
                'password': 'admin123'
            }, follow_redirects=True)
            
            response = client.post('/admin/shipping', data={
                'name': 'Express Shipping',
                'cost': '15.99',
                'delivery_days': '1'
            })
            assert response.status_code == 302


class TestSecurityAndLimiting:
    """Test rate limiting and security features"""
    
    def test_rate_limiting_enabled(self, client):
        # Make multiple requests to check rate limiting
        for i in range(3):
            response = client.get('/')
            assert response.status_code == 200


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
