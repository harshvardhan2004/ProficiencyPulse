# Skills Matrix Application

A modern web application for tracking employee skills, training requirements, and professional development. Built with Flask and Bootstrap 5, featuring a responsive design and comprehensive skill management capabilities.

## Features

### Core Functionality
- Track employee skills with proficiency levels (1-5 star rating)
- Manage training requirements and certification expiry dates
- View individual employee skill reports
- Search and filter functionality for employees and skills
- Responsive design with modern UI
- Pagination for large data sets
- Built-in user guide and help system

### User Interface
- Modern, responsive Bootstrap 5 design
- MBDA branded color scheme and styling
- Intuitive navigation system
- Interactive skill matrix dashboard
- Built-in user guide with separate sections for admins and users
- Direct email support link
- Mobile-friendly interface

### User Management
- Two-tier authentication system:
  - Admin users (email/password login)
  - Regular employees (clock ID login)
- "Remember me" functionality for persistent sessions (31-day duration)
- Role-based access control
- Admin user management through web interface
- Secure password handling and session management

### Admin Features
- Comprehensive admin dashboard
- Manage employees, skills, projects, and levels
- Add and edit employee details
- Define skill requirements and training expiry periods
- View comprehensive skill reports
- Manage organizational structure
- Add and remove admin users
- View all admin users in the system
- Search and pagination for skills management
- Bulk operations support

### Employee Features
- View and update personal skills
- Track training certifications
- View detailed skill reports
- Monitor training expiry dates
- Persistent login sessions with "Remember me" option
- Individual skill progress tracking
- Access to user guide and help system

## Technical Stack

- Backend: Flask (Python)
- Database: SQLAlchemy ORM
  - SQLite for development
  - MySQL for production
- Frontend: 
  - Bootstrap 5 for responsive design
  - Font Awesome icons
  - Modern UI components
  - Custom MBDA styling
- Authentication: Session-based with role management
- Production Server: Waitress WSGI server

## Installation

1. Clone the repository:
```bash
git clone [repository-url]
cd skills-matrix
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create environment file:
```bash
cp .env.example .env
```

5. Configure your .env file:
```ini
# Development Settings
FLASK_ENV=development
SECRET_KEY=your-secret-key-here

# Database Settings (MySQL for production)
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_HOST=localhost
DB_NAME=skills_matrix

# Server Settings
PORT=8000
```

## Database Setup

### Development (SQLite)
```bash
flask init-db
```

### Production (MySQL)
1. Create MySQL database:
```sql
CREATE DATABASE skills_matrix CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

2. Initialize database:
```bash
FLASK_ENV=production flask init-db
```

## Creating an Admin User

There are two ways to create admin users:

1. Using the command line (initial setup):
```bash
flask create-admin "admin@example.com" "Admin Name" "password"
```

2. Through the admin panel (requires existing admin access):
   - Log in as an admin
   - Navigate to the Admin Panel
   - Use the "Add Admin" button in the Admin Users section

## Running the Application

### Development
```bash
python wsgi.py
```

### Production
```bash
FLASK_ENV=production python wsgi.py
```

The application will be available at `http://localhost:8000` (or your configured port).

## Security Features

- Secure password hashing using Werkzeug
- HTTP-only session cookies
- CSRF protection with Flask-WTF
- Role-based access control
- Production-ready security settings
- Session persistence with "Remember Me" functionality
- Admin privilege management
- Protected admin routes
- Input validation and sanitization

## Database Management

### View Database Status
```bash
flask db-status
```

### Initialize/Update Database
```bash
flask init-db
```

### Reset Database (Caution!)
```bash
flask drop-db
```

## Project Structure
```
skills-matrix/
├── app.py              # Main application file
├── config.py           # Configuration management
├── database.py         # Database initialization
├── wsgi.py            # WSGI entry point
├── requirements.txt    # Python dependencies
├── .env.example       # Environment template
└── templates/         # HTML templates
    ├── base.html      # Base template with modern UI
    ├── index.html     # Skills matrix dashboard
    ├── login.html     # Authentication pages
    ├── admin.html     # Admin dashboard
    ├── employee_report.html  # Individual reports
    ├── user_guide.html      # Built-in help system
    └── update_skills.html    # Skill management
```

## Support and Help

- Built-in user guide accessible from the navigation bar
- Direct email support via "Get Help" button
- Support email: FTN.ISVDashboard@mbda.co.uk

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

[Your License Here]