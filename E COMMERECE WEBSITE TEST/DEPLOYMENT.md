# Al Amoodi E-Commerce Platform - Deployment Guide

## Production Checklist

### 1. Environment Setup
```bash
# Create .env file with all required variables
FLASK_SECRET_KEY=your-very-secret-key-generate-with-os.urandom
DATABASE_URL=postgresql://user:password@localhost/amoodi_db  # For production
STRIPE_SECRET_KEY=sk_live_your_stripe_key
STRIPE_PUBLISHABLE_KEY=pk_live_your_stripe_key
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_FROM_NUMBER=+1234567890
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password
FLASK_ENV=production
```

### 2. Database Setup (PostgreSQL recommended)

#### Install PostgreSQL
```bash
# Ubuntu/Debian
sudo apt-get install postgresql postgresql-contrib

# macOS
brew install postgresql
brew services start postgresql
```

#### Create database and user
```sql
CREATE DATABASE amoodi_db;
CREATE USER amoodi_user WITH PASSWORD 'secure_password';
ALTER ROLE amoodi_user SET client_encoding TO 'utf8';
ALTER ROLE amoodi_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE amoodi_user SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE amoodi_db TO amoodi_user;
```

#### Run migrations
```bash
flask db upgrade
```

### 3. Dependencies Installation
```bash
pip install -r requirements.txt
```

### 4. Gunicorn Setup (Production Server)

#### Install Gunicorn
```bash
pip install gunicorn
```

#### Create wsgi.py
```python
from app import app, db
if __name__ == "__main__":
    app.run()
```

#### Run with Gunicorn
```bash
gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app
```

### 5. Nginx Configuration

```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /static {
        alias /path/to/static;
    }
}
```

### 6. SSL/HTTPS with Let's Encrypt

```bash
sudo apt-get install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

### 7. Docker Deployment

#### Dockerfile
```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "wsgi:app"]
```

#### docker-compose.yml
```yaml
version: '3.8'
services:
  web:
    build: .
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://user:password@db/amoodi_db
    depends_on:
      - db
  
  db:
    image: postgres:13
    environment:
      POSTGRES_DB: amoodi_db
      POSTGRES_USER: amoodi_user
      POSTGRES_PASSWORD: secure_password
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

### 8. Heroku Deployment

#### Procfile
```
web: gunicorn wsgi:app
release: flask db upgrade
```

#### Create Heroku app
```bash
heroku create amoodi-store
heroku config:set FLASK_SECRET_KEY=your-secret
heroku config:set DATABASE_URL=your-postgres-url
heroku config:set STRIPE_SECRET_KEY=your-stripe-key
git push heroku main
```

### 9. AWS Deployment

#### Using Elastic Beanstalk
```bash
pip install awseb-cli
eb init -p python-3.10 amoodi-app
eb create amoodi-env
eb deploy
```

#### Using EC2
1. Launch t3.micro instance (free tier eligible)
2. Security group: allow HTTP (80), HTTPS (443), SSH (22)
3. SSH into instance and follow steps 2-6 above

### 10. Performance Optimization

#### Enable caching
```python
# In app.py
CACHE_TYPE = "simple"
CACHE_DEFAULT_TIMEOUT = 300
cache = Cache(app, config={'CACHE_TYPE': 'simple'})
```

#### Database optimization
- Create indexes on frequently queried columns:
```sql
CREATE INDEX idx_product_category ON product(category_id);
CREATE INDEX idx_order_user ON order(user_id);
CREATE INDEX idx_order_created ON order(created_at);
```

#### Static file optimization
- Use CDN (CloudFront, Cloudflare) for static assets
- Enable gzip compression in Nginx

### 11. Monitoring & Logging

#### Application monitoring
```bash
pip install sentry-sdk
```

#### Logging setup
```python
import logging
logging.basicConfig(
    filename='app.log',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s'
)
```

### 12. Security Best Practices

- [ ] Enable HTTPS/SSL
- [ ] Set secure cookies: `SESSION_COOKIE_SECURE = True`
- [ ] Set CSRF protection: use Flask-WTF
- [ ] Rate limit API endpoints
- [ ] Implement CORS properly
- [ ] Regular security updates
- [ ] Monitor for SQL injection vulnerabilities
- [ ] Use strong database passwords
- [ ] Implement regular backups

### 13. Backup Strategy

#### Automated backups
```bash
# PostgreSQL backup script
pg_dump amoodi_db > backup_$(date +%Y%m%d).sql
```

#### Backup to cloud storage (S3)
```bash
aws s3 cp backup.sql s3://my-backup-bucket/
```

### 14. Troubleshooting

**502 Bad Gateway**
- Check Gunicorn is running: `ps aux | grep gunicorn`
- Check logs: `tail -f /var/log/nginx/error.log`

**Database connection failed**
- Verify DATABASE_URL environment variable
- Check PostgreSQL is running: `systemctl status postgresql`

**Email not sending**
- Verify SMTP credentials
- Check firewall allows port 587/465
- Enable "Less secure apps" for Gmail or use app-specific password

## Testing Before Production

```bash
# Run test suite
pytest test_app.py -v

# Load testing
locust -f locustfile.py --host=http://localhost:5000
```

## Monitoring Commands

```bash
# Monitor resource usage
top
df -h
free -m

# Monitor Nginx
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log

# Monitor application
tail -f app.log
```
