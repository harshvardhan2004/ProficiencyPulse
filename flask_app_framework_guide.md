# Flask Web Application Development Framework Guide

## Application Overview
This guide outlines the framework used to build a modern Flask web application with role-based authentication, database management, and a responsive UI.

### Core Technologies
- Backend: Flask 3.0.0 with Python 3.x
- Database: SQLAlchemy 2.0.23 with Flask-SQLAlchemy 3.1.1
- Authentication: Flask session-based with role management
- Forms: Flask-WTF 1.2.1 for CSRF protection
- Frontend: Bootstrap 5 with Font Awesome icons
- Production Server: Waitress 2.1.2
- Database Drivers: PyMySQL 1.1.0 with cryptography 41.0.7
- Environment: python-dotenv 1.0.0

### Project Structure
```
skills-matrix/
├── app.py              # Main application with routes and models
├── config.py           # Environment-specific configurations
├── database.py         # Database initialization and management
├── wsgi.py            # WSGI entry point for development/production
├── requirements.txt    # Python dependencies
├── .env               # Environment variables (not in version control)
├── .env.example       # Environment template
└── templates/         # Jinja2 HTML templates
    ├── base.html      # Base template with navigation and styling
    ├── index.html     # Main dashboard/matrix view
    ├── login.html     # Authentication page
    ├── admin.html     # Admin dashboard
    └── components/    # Reusable template components
```

### Key Components

1. Configuration Management (config.py):
```python
class Config:
    SECRET_KEY = environ.get('SECRET_KEY', 'dev-key')
    SQLALCHEMY_DATABASE_URI = environ.get('DATABASE_URL', 'sqlite:///app.db')
    PERMANENT_SESSION_LIFETIME = timedelta(days=31)
    SESSION_COOKIE_SECURE = environ.get('FLASK_ENV') == 'production'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///skills_matrix.db'

class ProductionConfig(Config):
    DEBUG = False
    DB_USER = os.getenv('DB_USER', 'root')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_NAME = os.getenv('DB_NAME', 'skills_matrix')
    SQLALCHEMY_DATABASE_URI = f'mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}'
```

2. Database Setup (database.py):
```python
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect

db = SQLAlchemy()

def init_db(app):
    """Initialize the database with the app"""
    db.init_app(app)
    
    with app.app_context():
        engine = db.get_engine()
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        
        # Create only missing tables
        db.Model.metadata.create_all(
            bind=engine,
            tables=[table for table in db.Model.metadata.tables.values()
                   if table.name not in existing_tables]
        )
```

3. WSGI Entry Point (wsgi.py):
```python
from dotenv import load_dotenv
from app import app
import os

load_dotenv()

if __name__ == "__main__":
    env = os.getenv('FLASK_ENV', 'production')
    host = os.getenv('FLASK_HOST', '127.0.0.1')
    port = int(os.getenv('FLASK_PORT', 5000))
    
    if env == 'development':
        app.run(host=host, port=port, debug=True)
    else:
        from waitress import serve
        serve(
            app,
            host=host,
            port=port,
            threads=int(os.getenv('WAITRESS_THREADS', 4)),
            connection_limit=int(os.getenv('WAITRESS_CONNECTION_LIMIT', 1000)),
            channel_timeout=int(os.getenv('WAITRESS_CHANNEL_TIMEOUT', 30))
        )
```

4. Authentication System:
```python
# Decorators for route protection
def admin_required(f):
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin', False):
            flash('Access denied. Administrator privileges required.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def login_required(f):
    def decorated_function(*args, **kwargs):
        if 'employee_id' not in session:
            flash('Please log in first.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function
```

### Development Best Practices

1. Environment Configuration:
```ini
# .env.example
FLASK_ENV=development
FLASK_HOST=127.0.0.1
FLASK_PORT=5000
SECRET_KEY=your-secure-secret-key-here

# Database Configuration
DB_USER=your_mysql_user
DB_PASSWORD=your_mysql_password
DB_HOST=localhost
DB_NAME=skills_matrix

# Production Settings
WAITRESS_THREADS=4
WAITRESS_CONNECTION_LIMIT=1000
WAITRESS_CHANNEL_TIMEOUT=30
```

2. Database Models:
```python
class Employee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    is_admin = db.Column(db.Boolean, default=False)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
```

3. CLI Commands:
```python
@app.cli.command("init-db")
def init_db_command():
    """Initialize the database and create missing tables."""
    try:
        db.create_all()
        click.echo('Database initialized successfully.')
    except Exception as e:
        click.echo(f'Error initializing database: {str(e)}', err=True)

@app.cli.command("create-admin")
@click.argument('email')
@click.argument('name')
@click.argument('password')
def create_admin_command(email, name, password):
    """Create an administrator user."""
    try:
        admin = Employee(
            email=email,
            name=name,
            is_admin=True
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        click.echo('Admin user created successfully.')
    except Exception as e:
        db.session.rollback()
        click.echo(f'Error creating admin: {str(e)}', err=True)
```

### Security Features

1. Session Management:
- 31-day session lifetime with "Remember Me"
- Secure cookie settings
- CSRF protection
- HTTP-only cookies
- SameSite cookie policy

2. Password Security:
- Werkzeug password hashing
- No plain-text password storage
- Secure password reset flow

3. Access Control:
- Role-based authentication
- Protected admin routes
- Session validation
- Input sanitization

### Deployment Steps

1. Server Setup:
```bash
# Install dependencies
pip install -r requirements.txt

# Initialize database
flask init-db

# Create initial data
flask init-data

# Create admin user
flask create-admin "admin@example.com" "Admin Name" "password"
```

2. Production Configuration:
```ini
FLASK_ENV=production
SECRET_KEY=your-secure-key
DB_USER=production_user
DB_PASSWORD=secure_password
DB_HOST=database_host
DB_NAME=skills_matrix
```

3. Running in Production:
```bash
python wsgi.py
```

### Error Handling

1. Database Errors:
```python
try:
    db.session.commit()
    flash('Operation successful!', 'success')
except Exception as e:
    db.session.rollback()
    flash(f'Error: {str(e)}', 'error')
```

2. Form Validation:
```python
if not name or not email:
    flash('All fields are required.', 'error')
    return redirect(url_for('add_employee'))
```

3. Authentication Errors:
```python
if not employee or not employee.check_password(password):
    flash('Invalid credentials.', 'error')
    return redirect(url_for('login'))
```

This framework provides a robust foundation for building secure, scalable Flask applications with modern features and best practices. The modular structure allows for easy maintenance and future enhancements. 