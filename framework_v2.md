# Flask Web Application Development Framework Guide

This guide outlines a **generalized framework** for building a modern Flask web application with role-based authentication, database management, and a responsive UI. It’s based on the structure and practices of the sample “Skills Matrix” application, but has been **adapted for broader reuse**.

---

## Core Technologies

1. **Flask 3.0.0** — Main web framework  
2. **SQLAlchemy 2.0.23 + Flask-SQLAlchemy 3.1.1** — ORM-based database access  
3. **python-dotenv 1.0.0** — Environment variable loading  
4. **Forms & CSRF**: Flask-WTF 1.2.1  
5. **Waitress 2.1.2** — Production WSGI server  
6. **PyMySQL 1.1.0 & cryptography 41.0.7** — MySQL driver with modern TLS support  
7. **Bootstrap 5 & Font Awesome** — Frontend styling and icons  

---

## Typical Project Structure

```
my_flask_app/
├── app.py              # Main application with routes & models
├── config.py           # Environment-specific configurations
├── database.py         # Database initialization and management
├── wsgi.py             # WSGI entry point (development & production)
├── requirements.txt    # Python dependencies
├── .env                # Environment variables (ignored by VCS)
├── .env.example        # Example environment file
└── templates/          # Jinja2 HTML templates
    ├── base.html
    ├── login.html
    ├── admin.html
    ├── index.html
    └── ... (other templates)
```

> *Note:* You can rename folders and files (e.g., rename `my_flask_app` to suit your use case, or separate routes, models, etc., into different modules).

---

## 1. Configuration Management (`config.py`)

A **Config** class approach allows easy switching between development and production. Below is a generalized example:

```python
import os
from os import environ
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()  # Load from .env if available

class Config:
    SECRET_KEY = environ.get('SECRET_KEY', 'dev-key')
    # Default to SQLite for dev/fallback; override with MySQL in production
    SQLALCHEMY_DATABASE_URI = environ.get('DATABASE_URL', 'sqlite:///app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Session settings
    PERMANENT_SESSION_LIFETIME = timedelta(days=31)
    SESSION_COOKIE_SECURE = environ.get('FLASK_ENV') == 'production'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

class DevelopmentConfig(Config):
    DEBUG = True
    # Example: local SQLite DB
    SQLALCHEMY_DATABASE_URI = 'sqlite:///app_dev.db'

class ProductionConfig(Config):
    DEBUG = False
    # MySQL in production
    DB_USER = environ.get('DB_USER', 'root')
    DB_PASSWORD = environ.get('DB_PASSWORD', '')
    DB_HOST = environ.get('DB_HOST', 'localhost')
    DB_NAME = environ.get('DB_NAME', 'my_app_db')
    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
    )

# Choose config based on FLASK_ENV or default to ProductionConfig
env = environ.get('FLASK_ENV', 'production')
config = ProductionConfig if env == 'production' else DevelopmentConfig
```

> *Tip:* Keep secrets (API keys, DB passwords, etc.) out of version control by using `.env` files.

---

## 2. Database Setup (`database.py`)

Use a helper function `init_db(app)` to tie SQLAlchemy to your Flask application. Only create tables that don’t already exist:

```python
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect

db = SQLAlchemy()

def init_db(app):
    db.init_app(app)
    with app.app_context():
        engine = db.get_engine()
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        
        db.Model.metadata.create_all(
            bind=engine,
            tables=[
                table for table in db.Model.metadata.tables.values()
                if table.name not in existing_tables
            ]
        )
```

> *Note:* For local development, you might rely on SQLite. For production, you’ll use MySQL. This pattern supports both.

---

## 3. WSGI Entry Point (`wsgi.py`)

This file decides whether to run the **Flask built-in development server** or use the **Waitress** server for production.

```python
import os
from dotenv import load_dotenv
from app import app

load_dotenv()

if __name__ == "__main__":
    env = os.getenv('FLASK_ENV', 'production')
    host = os.getenv('FLASK_HOST', '127.0.0.1')
    port = int(os.getenv('FLASK_PORT', 5000))

    if env == 'development':
        # Dev server (Flask)
        app.run(host=host, port=port, debug=True)
    else:
        # Production server (Waitress)
        from waitress import serve
        serve(
            app,
            host=host,
            port=port,
            threads=int(os.getenv('WAITRESS_THREADS', 4)),
            connection_limit=int(os.getenv('WAITRESS_CONNECTION_LIMIT', 1000)),
            channel_timeout=int(os.getenv('WAITRESS_CHANNEL_TIMEOUT', 30)),
        )
```

---

## 4. Authentication System

Below is a sample pattern using session-based authentication and custom decorators for role protection:

```python
from flask import session, flash, redirect, url_for
from functools import wraps

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in first.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin', False):
            flash('Access denied. Admin only.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function
```

### Example `User` model snippet

```python
from werkzeug.security import generate_password_hash, check_password_hash

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    is_admin = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
```

---

## Development Best Practices

1. **Use a `.env` File**  
   Keep local development settings in `.env`. Example:

   ```ini
   FLASK_ENV=development
   FLASK_HOST=127.0.0.1
   FLASK_PORT=5000
   SECRET_KEY=super-secret-dev-key

   # Database
   DB_USER=your_mysql_user
   DB_PASSWORD=your_mysql_password
   DB_HOST=localhost
   DB_NAME=my_app_db

   # Production Settings
   WAITRESS_THREADS=4
   WAITRESS_CONNECTION_LIMIT=1000
   WAITRESS_CHANNEL_TIMEOUT=30
   ```

2. **CSRF Protection**  
   If you use forms, integrate Flask-WTF to guard against CSRF.  

3. **Keep secrets safe**  
   Do not commit `.env` to version control.

4. **Use migrations** (optional)  
   While this example uses `db.create_all()`, you can incorporate **Flask-Migrate** for more advanced schema changes.

---

## CLI Commands

Use Flask’s custom CLI commands for common database tasks. Below are some typical ones:

```python
import click
from your_app_package.database import db

@app.cli.command("init-db")
def init_db_command():
    """Initialize the database and create missing tables."""
    with app.app_context():
        db.create_all()
        click.echo('Database initialized successfully.')

@app.cli.command("drop-db")
@click.confirmation_option(
    prompt='Are you sure you want to drop all tables? This will delete all data!'
)
def drop_db_command():
    """Drop all database tables after confirmation."""
    with app.app_context():
        db.drop_all()
        click.echo('All tables dropped.')

@app.cli.command("create-admin")
@click.argument('email')
@click.argument('name')
@click.argument('password')
def create_admin_command(email, name, password):
    """Create an administrator user."""
    from your_app_package.models import User  # or wherever your model is
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if user:
            click.echo(f'User with email {email} already exists.')
            return

        admin_user = User(email=email, is_admin=True)
        admin_user.set_password(password)
        db.session.add(admin_user)
        db.session.commit()
        click.echo('Admin user created successfully.')
```

> *Tip:* Adjust the user model name or fields as needed.

---

## Security Features

1. **Session Management**  
   - Up to 31-day session lifetimes (configurable)  
   - HTTP-only cookies to protect from JavaScript-based exploits  
   - `SESSION_COOKIE_SECURE` in production to ensure HTTPS usage  

2. **Password Security**  
   - Store only hashed passwords (e.g., Werkzeug’s `generate_password_hash`)  
   - `check_password_hash` for comparisons  

3. **Access Control**  
   - `@login_required` and `@admin_required` decorators  
   - Appropriately check user roles  

4. **CSRF Protection**  
   - Use `FlaskForm` from Flask-WTF  
   - Insert `{{ form.hidden_tag() }}` in your Jinja2 templates  

---

## Deployment Steps

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Initialize the database**:
   ```bash
   flask init-db
   ```

3. **(Optional) Seed basic data**:
   ```bash
   # If you have a custom CLI command for creating initial roles, levels, etc.
   flask init-data  
   ```

4. **Create your first admin user**:
   ```bash
   flask create-admin "admin@example.com" "Admin User" "password123"
   ```

5. **Run in development**:
   ```bash
   python wsgi.py
   # or
   flask run
   ```

6. **Run in production**:
   - Set `FLASK_ENV=production` in `.env`  
   - Start with Waitress:
     ```bash
     python wsgi.py
     ```

---

## Error Handling & Validation

1. **Database Errors**  
   Roll back on exceptions:
   ```python
   try:
       db.session.commit()
   except Exception as e:
       db.session.rollback()
       flash(str(e), 'error')
   ```

2. **Form Validation**  
   ```python
   if not form.validate_on_submit():
       flash('Please correct the errors.', 'error')
       return redirect(url_for('some_form'))
   ```

3. **Authentication Errors**  
   ```python
   user = User.query.filter_by(email=email).first()
   if not user or not user.check_password(password):
       flash('Invalid credentials.', 'error')
       return redirect(url_for('login'))
   ```

---

## Extending & Customizing

This framework is a **foundation** for building any Flask app that requires:

- User authentication (admin vs. standard users)
- Integration with both SQLite (for dev) and MySQL (for production)
- Session-based access control
- Modern, responsive UI with Bootstrap
- Reusable CLI commands for database management

**You can rename** models (e.g., `Employee` to `User`) or entire routes to match your domain. Likewise, you can add more tables, handle file uploads, integrate with external APIs, etc. The point is to maintain the same high-level structure to keep your application well-organized and secure.

---

## Conclusion

By following these guidelines—**clean project structure**, **environment-based config**, **SQLAlchemy integration**, **role-based authentication**, and **CLI-driven database commands**—you can quickly develop a **scalable, maintainable** Flask application. Feel free to tailor it to **any domain** beyond the “Skills Matrix” example.