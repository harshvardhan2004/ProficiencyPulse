# Skills Matrix Application

A modern web application for tracking employee skills, training requirements, professional development, and organizational structure. Built with Flask and Bootstrap 5, featuring a responsive design, comprehensive management capabilities, and auditing features.

## Features

### Core Functionality
- Track employee skills with proficiency levels (1-5 rating)
- Manage training requirements, categories, details, and certification expiry dates
- View individual employee skill reports and job history
- Visualize the organizational structure with an interactive org chart
- Comprehensive search and filtering for employees (name, title, email, clock ID, project) and skills
- Filter employees by specific skills and minimum proficiency levels
- Export filtered employee lists to CSV format
- Responsive design with a modern UI using Bootstrap 5
- Pagination for large data sets (employees, skills, audit logs)
- Built-in user guide and configurable help system (via email link)
- Audit trail logging user actions (logins, updates, deletes, etc.)
- Database backup and restore functionality

### User Interface
- Modern, responsive Bootstrap 5 design
- Company-branded color scheme and styling (customizable in `base.html`)
- Intuitive navigation system
- Interactive skill matrix dashboard
- Modals for adding/editing skills, projects, levels, and admins
- Built-in user guide modal with separate sections for standard users and admins
- Direct email support link in the navigation bar (configurable)
- Mobile-friendly interface

### User & Profile Management
- Two-tier authentication system:
  - Admin users (email/password login)
  - Regular employees (clock ID login - no password needed)
- User profile page for viewing and updating personal details (email, phone, LinkedIn, about me)
- "Remember me" functionality for persistent sessions (configurable duration)
- Role-based access control (Standard User vs. Admin)
- Secure password hashing (Werkzeug) and session management (Flask sessions)

### Admin Features
- Comprehensive admin dashboard with tabbed interface
- **Employee Management:**
    - Add, edit, and delete non-admin employees
    - View employee details, job history, and skill reports
    - Assign employees to projects, levels, and managers
    - Manage admin user accounts (add admins, remove admin privileges)
- **Skills Management:**
    - Add, edit, and delete skills
    - Define skill descriptions, training requirements (mandatory, expiry months, details), and training categories
- **Options Management:**
    - Create and delete projects
    - Create and delete employee levels/grades, defining their order
    - Configure system settings (e.g., "Get Help" email address)
- **Tools:**
    - Download database backups (SQLite format)
    - Restore database from backup files (overwrites current data)
- **Audit Log:**
    - View a chronological log of system actions with user details, timestamps, and change details

### Employee Features
- View personal skills matrix on the dashboard
- Update personal skill proficiency levels and add notes
- Record training completion dates for required skills
- View personal skill report including proficiency, training status, and job history
- Monitor training expiry dates
- Edit personal profile information
- View the organizational chart
- Access the user guide and help system

## Technical Stack

- **Backend:** Python 3 with Flask framework
- **Database:** SQLAlchemy ORM
    - Development: SQLite (default `skills_matrix.db`)
    - Production: MySQL (configurable via `.env`, requires `PyMySQL`) or other SQLAlchemy-supported DB.
- **Database Migrations:** Flask-Migrate (using Alembic)
- **Templating:** Jinja2 (via Flask)
- **Frontend:**
    - Bootstrap 5 for layout and components
    - Font Awesome 6 for icons
    - Vanilla JavaScript for minor interactions (e.g., modal triggers, dynamic form fields)
    - Google Charts for the Organization Chart
- **Forms:** Flask-WTF with WTForms
- **Authentication:** Flask sessions, Werkzeug password hashing
- **WSGI Server (Production):** Waitress (configured in `wsgi.py`)
- **Configuration:** `python-dotenv` for environment variables

## Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd skills-matrix
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python -m venv venv
    # On Windows:
    # venv\Scripts\activate
    # On macOS/Linux:
    # source venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    # If using MySQL for production, uncomment PyMySQL in requirements.txt first
    ```

4.  **Create environment file:**
    Copy the example environment file:
    ```bash
    cp .env.example .env
    ```

5.  **Configure your `.env` file:**
    Edit the `.env` file with your specific settings:
    ```ini
    # Flask Configuration
    FLASK_ENV=development # Change to 'production' for production
    SECRET_KEY=your-very-secret-and-strong-key # CHANGE THIS!

    # Database Configuration (Example for SQLite - default)
    # DATABASE_URL=sqlite:///skills_matrix.db

    # Database Configuration (Example for MySQL - uncomment and configure for production)
    # FLASK_ENV=production
    # DB_USER=your_mysql_user
    # DB_PASSWORD=your_mysql_password
    # DB_HOST=localhost
    # DB_NAME=skills_matrix
    # SQLALCHEMY_DATABASE_URI=mysql+pymysql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}/${DB_NAME}

    # Server Configuration (used by wsgi.py)
    FLASK_HOST=127.0.0.1
    FLASK_PORT=5000

    # Production Settings (Waitress - used when FLASK_ENV=production)
    WAITRESS_THREADS=4
    WAITRESS_CONNECTION_LIMIT=1000
    WAITRESS_CHANNEL_TIMEOUT=30
    ```
    *   **Important:** Change `SECRET_KEY` to a long, random string for security.
    *   Configure database settings based on your environment (SQLite for development, MySQL or other for production).

## Database Setup and Initialization

This project uses Flask-Migrate (Alembic) for handling database schema changes.

1.  **Initialize the Database (First time setup):**
    If you haven't already, initialize the Flask-Migrate environment (this creates the `migrations` directory):
    ```bash
    flask db init
    ```
    *Note: The `migrations` directory is already included in the provided code, so this step might only be needed if starting from scratch.*

2.  **Create Initial Migration (If needed):**
    If `migrations/versions` is empty or you've made model changes before the first migration:
    ```bash
    flask db migrate -m "Initial database schema"
    ```

3.  **Apply Migrations:**
    This command applies all pending migrations to create or update your database tables according to the models defined in `app.py`.
    ```bash
    flask db upgrade
    ```
    *   For production using MySQL, ensure the database (`skills_matrix` in the example) exists *before* running `flask db upgrade`.
        ```sql
        -- Example SQL to create the database in MySQL:
        CREATE DATABASE skills_matrix CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
        ```

4.  **Initialize Basic Data:**
    Populate the database with essential starting data like default levels and the "Unassigned" project.
    ```bash
    flask init-data
    ```

5.  **Create Your First Admin User:**
    You need an admin user to manage the application.
    ```bash
    flask create-admin "your_admin_email@example.com" "Your Admin Name" "your_secure_password"
    ```
    Replace the email, name, and password with your desired credentials.

**Order is Important:** Run the commands in the sequence: `db upgrade`, `init-data`, `create-admin`.

## Running the Application

The `wsgi.py` file handles running the application in both development and production modes based on the `FLASK_ENV` environment variable.

*   **Development Mode (using Flask's built-in server):**
    Ensure `FLASK_ENV=development` in your `.env` file.
    ```bash
    python wsgi.py
    ```
    The application will be available at `http://127.0.0.1:5000` (or your configured host/port). Debug mode will be enabled.

*   **Production Mode (using Waitress WSGI server):**
    Set `FLASK_ENV=production` in your `.env` file and configure your production database settings.
    ```bash
    python wsgi.py
    ```
    Waitress will serve the application on the configured host/port. Debug mode will be disabled.

## Usage

1.  **Login:**
    *   Navigate to the application URL.
    *   **Admins:** Enter your email and password.
    *   **Standard Users:** Enter your assigned Clock ID (no password needed).
    *   Check "Remember me" to stay logged in longer.
2.  **Dashboard (`/`):** View the main skills matrix. Admins see all users with filtering/search; standard users see their own entry.
3.  **Update Skills:** Click the "Skills" button on your row (or navigate if logged in) to rate proficiency, add training dates, and notes.
4.  **Profile (`/profile`):** View and update your email, phone, LinkedIn, and 'About Me' section.
5.  **Org Chart (`/org-chart`):** View the interactive organization structure.
6.  **Admin Panel (`/admin`):** Access admin functions via tabs (Employee Management, Skills Management, Options Management, Tools, Audit Log link).

## Security Features

- Secure password hashing for admin users using `Werkzeug.security`.
- Session management using Flask's secure cookies.
    - `SESSION_COOKIE_SECURE` (enabled in production)
    - `SESSION_COOKIE_HTTPONLY` (enabled)
    - `SESSION_COOKIE_SAMESITE='Lax'` (enabled)
- CSRF protection implicitly provided by Flask-WTF forms.
- Role-based access control using `@admin_required` and `@login_required` decorators.
- Input validation using WTForms validators.
- Audit logging of key user actions.
- Parameterized queries via SQLAlchemy ORM help prevent SQL injection.

## Database Management Commands

The application provides custom Flask CLI commands for database operations:

*   `flask db-status`: Show existing tables in the database.
*   `flask init-db`: Creates tables defined in models if they don't exist (uses `db.create_all()` selectively). *Note: `flask db upgrade` is the preferred method for schema management.*
*   `flask drop-db`: Drops all tables (requires confirmation, **use with caution!**).
*   `flask init-data`: Populates initial levels and projects.
*   `flask create-admin <email> <name> <password>`: Creates a new admin user.

Standard Flask-Migrate commands are also essential:

*   `flask db migrate -m "Description of changes"`: Generate a new migration script after changing models.
*   `flask db upgrade`: Apply pending migrations to the database.
*   `flask db downgrade`: Revert the last migration (use carefully).

## Project Structure

```
/
├── .env.example            # Example environment variables
├── .repomix/               # (Tool specific, may not be needed in repo)
├── app.py                  # Main Flask application, models, routes
├── config.py               # Configuration classes (Development/Production)
├── database.py             # SQLAlchemy setup (db object)
├── migrations/             # Flask-Migrate/Alembic migration files
│   ├── versions/           # Individual migration scripts
│   ├── alembic.ini         # Alembic configuration
│   ├── env.py              # Alembic environment setup
│   ├── README              # Alembic README
│   └── script.py.mako      # Migration script template
├── README.md               # This file
├── requirements.txt        # Python dependencies
├── static/                 # (Optional: for CSS/JS if not using CDN)
├── templates/              # Jinja2 HTML templates
│   ├── _*.html             # Partial templates (included in others)
│   ├── add_employee.html
│   ├── add_skill.html      # (Now integrated into admin modal)
│   ├── admin.html
│   ├── audit_log.html
│   ├── base.html           # Base template with nav, styles
│   ├── edit_employee.html
│   ├── employee_report.html
│   ├── index.html          # Main dashboard/matrix view
│   ├── login.html
│   ├── org_chart.html
│   ├── profile.html
│   ├── update_skills.html
│   └── user_guide.html     # Content for the user guide modal
└── wsgi.py                 # WSGI entry point (for dev/prod server)
```

## Configuration Details

Key configuration options are managed via the `.env` file and loaded in `config.py`:

*   `FLASK_ENV`: Set to `development` or `production`. Controls debug mode, database URI selection, and security settings.
*   `SECRET_KEY`: **Crucial for security.** A long, random string used for session signing. Keep this secret.
*   `SQLALCHEMY_DATABASE_URI`: Specifies the database connection string. Automatically switches between SQLite (dev) and MySQL (prod based on `FLASK_ENV`), but can be explicitly set.
*   `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_NAME`: Used to construct the MySQL URI in `ProductionConfig`.
*   `FLASK_HOST`, `FLASK_PORT`: Network interface and port for the server.
*   `WAITRESS_*`: Configuration for the Waitress production server (threads, connection limits, timeouts).
*   `PERMANENT_SESSION_LIFETIME`: How long the "Remember me" session lasts (defaults to 31 days).

The "Get Help" email address is stored in the `configuration` database table (key: `help_email`) and can be updated via the Admin Panel -> Options Management tab.

## Contributing

Contributions are welcome! Please follow these steps:

1.  Fork the repository.
2.  Create a new branch for your feature or bug fix (`git checkout -b feature/your-feature-name`).
3.  Make your changes and commit them (`git commit -m 'Add some feature'`).
4.  Push your changes to your fork (`git push origin feature/your-feature-name`).
5.  Open a Pull Request against the main repository branch.

Please ensure your code follows standard Python style guidelines (e.g., PEP 8) and includes relevant updates to documentation or tests if applicable.

## License

[Specify Your License Here - e.g., MIT License, Apache 2.0]

---

*This README was generated based on the project structure and code analysis.*