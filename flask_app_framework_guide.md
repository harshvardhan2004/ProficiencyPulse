# Flask Skills Matrix Application Framework Guide

## Overview
This guide outlines the framework used to build a comprehensive skills matrix web application using Flask. The application features role-based authentication, employee skills management, and a responsive UI with Bootstrap 5.

## Core Technologies
- Flask (2.0+)
- SQLAlchemy (1.4+)
- Bootstrap 5
- Waitress (Production Server)
- MySQL (Production) / SQLite (Development)
- Font Awesome 5 (Icons)

## Project Structure
```
skills_matrix/
├── app.py                 # Main application file
├── config.py             # Configuration management
├── database.py           # Database initialization and management
├── wsgi.py              # WSGI entry point
├── requirements.txt      # Python dependencies
├── .env                 # Environment variables
├── static/              # Static assets (CSS, JS, images)
└── templates/           # Jinja2 HTML templates
    ├── base.html        # Base template with common layout
    ├── index.html       # Skills matrix main view
    ├── admin.html       # Admin panel with tabbed interface
    ├── login.html       # Authentication page
    ├── _admin_users_table.html    # Admin users partial
    ├── _employee_table.html       # Employees partial
    ├── _skills_table.html         # Skills partial
    ├── _projects_table.html       # Projects partial
    ├── _levels_table.html         # Levels partial
    └── _admin_modals.html         # Admin modals partial
```

## Key Features

### Authentication System
- Role-based authentication (Admin/Employee)
- Secure password hashing with Werkzeug
- "Remember Me" functionality
- Session management
- Protected routes with decorators

### Admin Panel
The admin panel is organized into four main sections:

1. Employee Management
   - Admin user management
   - Employee CRUD operations
   - Searchable employee list with pagination
   - Employee skill reports

2. Skills Management
   - Skill CRUD operations
   - Training requirements tracking
   - Searchable skills list with pagination
   - Training validity periods

3. Options Management
   - Project management
   - Employee level management
   - Hierarchical organization structure

4. Tools
   - Database backup/restore functionality
   - System maintenance tools

### Database Management
- Automatic database initialization
- Migration support
- Backup and restore functionality
- Data preservation during updates

## Implementation Details

### Configuration Management
```python
class Config:
    SECRET_KEY = os.getenv('SECRET_KEY')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    REMEMBER_COOKIE_DURATION = timedelta(days=30)
    
class DevelopmentConfig(Config):
    SQLALCHEMY_DATABASE_URI = 'sqlite:///skills.db'
    DEBUG = True

class ProductionConfig(Config):
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
    DEBUG = False
```

### Database Models
```python
class Employee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200))
    is_admin = db.Column(db.Boolean, default=False)
    clock_id = db.Column(db.String(20))
    job_title = db.Column(db.String(100))
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'))
    level_id = db.Column(db.Integer, db.ForeignKey('level.id'))
    skills = db.relationship('EmployeeSkill', backref='employee', lazy=True)

class Skill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    requires_training = db.Column(db.Boolean, default=False)
    training_expiry_months = db.Column(db.Integer)
    training_details = db.Column(db.Text)

class EmployeeSkill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'))
    skill_id = db.Column(db.Integer, db.ForeignKey('skill.id'))
    level = db.Column(db.Integer)
    notes = db.Column(db.Text)
    training_date = db.Column(db.DateTime)
```

### Authentication Decorators
```python
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'employee_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'employee_id' not in session:
            return redirect(url_for('login'))
        employee = Employee.query.get(session['employee_id'])
        if not employee or not employee.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function
```

## Development Best Practices

### Environment Management
- Use `.env` files for configuration
- Separate development and production settings
- Secure credential management

### Database Interactions
- Use SQLAlchemy ORM for database operations
- Implement proper transaction management
- Handle foreign key constraints

### Security Measures
- CSRF protection on forms
- Secure password handling
- Role-based access control
- Session security

### Frontend Development
- Responsive design with Bootstrap 5
- Progressive enhancement
- Client-side validation
- AJAX for dynamic updates

### Code Organization
- Modular template structure
- Separation of concerns
- Clear naming conventions
- Comprehensive commenting

## Deployment

### Server Setup
1. Install required packages
2. Configure environment variables
3. Initialize database
4. Set up Waitress server

### Environment Variables
```
FLASK_APP=wsgi.py
FLASK_ENV=production
SECRET_KEY=your-secret-key
DATABASE_URL=mysql://user:pass@localhost/skills
PORT=8080
```

### Database Initialization
```bash
# Initialize database tables
flask init-db

# Create initial data
flask init-data

# Create first admin user
flask create-admin "admin@example.com" "Admin Name" "password"
```

### Running the Application
Development:
```bash
flask run
```

Production:
```bash
python wsgi.py
```

## Error Handling
- Custom error pages (404, 403, 500)
- Graceful error handling
- User-friendly error messages
- Logging system

## Maintenance
- Regular database backups
- System monitoring
- Performance optimization
- Security updates

## Future Enhancements
- API integration
- Advanced reporting
- Bulk data operations
- Enhanced search capabilities
- Training management system
- Email notifications
- Automated skill assessments 