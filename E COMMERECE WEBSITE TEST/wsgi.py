"""
WSGI entry point for production deployment
Use with: gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app
"""
from app import app, db

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run()
