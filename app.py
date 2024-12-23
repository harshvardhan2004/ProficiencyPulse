# Flask Skills Matrix Application
# This application manages employee skills, training, and professional development
# Author: [Your Name]
# Version: 1.0

# Standard library imports
from datetime import datetime

# Third-party imports
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import inspect, or_
from sqlalchemy.orm import joinedload
import click

# Local application imports
from config import config
from database import db, init_db

# Initialize Flask application
app = Flask(__name__)
app.config.from_object(config)
init_db(app)

#------------------------------------------------------------------------------
# Database Models
#------------------------------------------------------------------------------

class Level(db.Model):
    """
    Employee level/grade in the organization.
    Used for hierarchical organization and career progression tracking.
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    order = db.Column(db.Integer, nullable=False)  # For sorting levels in correct order
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    employees = db.relationship('Employee', backref='level_rel', lazy=True)

class Project(db.Model):
    """
    Projects that employees can be assigned to.
    Tracks current project assignments and team composition.
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    employees = db.relationship('Employee', backref='project_rel', lazy=True)

class Employee(db.Model):
    """
    Core employee model containing personal and professional information.
    Handles both regular employees and administrators.
    """
    id = db.Column(db.Integer, primary_key=True)
    # Personal Information
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    clock_id = db.Column(db.String(50), unique=True)
    
    # Authentication and Authorization
    password_hash = db.Column(db.String(256))  # Only for admin users
    is_admin = db.Column(db.Boolean, default=False)
    
    # Professional Information
    job_title = db.Column(db.String(100), nullable=False)
    level_id = db.Column(db.Integer, db.ForeignKey('level.id'), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'))
    start_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    skills = db.relationship('EmployeeSkill', backref='employee', lazy=True)

    def set_password(self, password):
        """Hash and set the user's password (admin only)"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verify the user's password against stored hash"""
        return check_password_hash(self.password_hash, password)

class Skill(db.Model):
    """
    Defines skills that can be assigned to employees.
    Includes training requirements and expiry tracking.
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text)
    requires_training = db.Column(db.Boolean, default=False)
    training_expiry_months = db.Column(db.Integer)  # Number of months before training expires
    training_details = db.Column(db.Text)  # Details about required training
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    employee_skills = db.relationship('EmployeeSkill', backref='skill', lazy=True)

class EmployeeSkill(db.Model):
    """
    Junction table linking employees to their skills.
    Tracks proficiency levels and training status.
    """
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
    skill_id = db.Column(db.Integer, db.ForeignKey('skill.id'), nullable=False)
    proficiency_level = db.Column(db.Integer, nullable=False)  # 1-5 scale
    last_training_date = db.Column(db.Date)  # Date of last training completion
    training_expiry_date = db.Column(db.Date)  # Calculated expiry date
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

#------------------------------------------------------------------------------
# CLI Commands for Database Management
#------------------------------------------------------------------------------

@app.cli.command("db-status")
def db_status_command():
    """Show database status and list existing tables."""
    try:
        inspector = inspect(db.engine)
        existing_tables = inspector.get_table_names()
        
        if not existing_tables:
            click.echo('No tables exist in the database.')
            return

        click.echo('Existing tables:')
        for table in existing_tables:
            click.echo(f'  - {table}')
            
    except Exception as e:
        click.echo(f'Error checking database status: {str(e)}', err=True)

@app.cli.command("init-db")
def init_db_command():
    """Initialize the database and create missing tables."""
    try:
        inspector = inspect(db.engine)
        existing_tables = inspector.get_table_names()
        
        if existing_tables:
            tables_list = '\n  - '.join(existing_tables)
            click.echo(f'The following tables already exist:\n  - {tables_list}')
            click.echo('Skipping creation of existing tables.')
            
            # Create only missing tables
            missing_tables = [table for table in db.Model.metadata.tables.values()
                            if table.name not in existing_tables]
            if missing_tables:
                click.echo('Creating missing tables:')
                for table in missing_tables:
                    click.echo(f'  - {table.name}')
                db.Model.metadata.create_all(bind=db.engine, tables=missing_tables)
                click.echo('Missing tables created successfully.')
            else:
                click.echo('No missing tables to create.')
        else:
            click.echo('No existing tables found. Creating all tables...')
            db.create_all()
            click.echo('All tables created successfully.')
            
    except Exception as e:
        click.echo(f'Error initializing database: {str(e)}', err=True)

@app.cli.command("drop-db")
@click.confirmation_option(prompt='Are you sure you want to drop all tables? This will delete all data!')
def drop_db_command():
    """Drop all database tables after confirmation."""
    try:
        inspector = inspect(db.engine)
        existing_tables = inspector.get_table_names()
        
        if not existing_tables:
            click.echo('No tables to drop.')
            return
            
        click.echo('Dropping the following tables:')
        for table in existing_tables:
            click.echo(f'  - {table}')
            
        db.drop_all()
        click.echo('All tables dropped successfully.')
    except Exception as e:
        click.echo(f'Error dropping tables: {str(e)}', err=True)

#------------------------------------------------------------------------------
# Authentication and Authorization
#------------------------------------------------------------------------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Handle user authentication for both admin and regular users.
    Admins login with email/password, regular users with clock ID only.
    """
    if request.method == 'POST':
        identifier = request.form.get('identifier')  # Can be email or clock_id
        password = request.form.get('password')
        remember = 'remember' in request.form
        
        # Try to find user by email or clock_id
        employee = Employee.query.filter(
            (Employee.email == identifier) | 
            (Employee.clock_id == identifier)
        ).first()
        
        if employee and employee.is_admin and employee.check_password(password):
            # Admin login - requires password verification
            session.permanent = remember  # Make session permanent if remember is checked
            session['employee_id'] = employee.id
            session['is_admin'] = True
            flash('Logged in successfully as administrator.', 'success')
            return redirect(url_for('admin'))
        elif employee and employee.clock_id == identifier:
            # Regular employee login - only requires clock ID
            session.permanent = remember  # Make session permanent if remember is checked
            session['employee_id'] = employee.id
            session['is_admin'] = False
            flash('Logged in successfully.', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid credentials.', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Clear user session and redirect to login page."""
    session.clear()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('login'))

# Security decorators for route protection
def admin_required(f):
    """Decorator to restrict routes to admin users only."""
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin', False):
            flash('Access denied. Administrator privileges required.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def login_required(f):
    """Decorator to restrict routes to authenticated users."""
    def decorated_function(*args, **kwargs):
        if 'employee_id' not in session:
            flash('Please log in first.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

#------------------------------------------------------------------------------
# Main Application Routes
#------------------------------------------------------------------------------

@app.route('/')
@login_required
def index():
    """
    Display the main skills matrix.
    Admins see all employees, regular users see only their own skills.
    Supports searching employees by name, job title, or project.
    """
    # Get search query
    search_query = request.args.get('search', '').strip()
    
    # Base query depending on user type
    if session.get('is_admin', False):
        query = Employee.query
    else:
        query = Employee.query.filter_by(id=session.get('employee_id'))
    
    # Apply search if query exists
    if search_query:
        search = f"%{search_query}%"
        query = query.join(Project, Employee.project_id == Project.id, isouter=True).filter(
            db.or_(
                Employee.name.ilike(search),
                Employee.job_title.ilike(search),
                Employee.email.ilike(search),
                Project.name.ilike(search)
            )
        )
    
    # Get filtered employees
    employees = query.all()
    
    skills = Skill.query.all()
    today = datetime.utcnow().date()
    return render_template('index.html', 
                         employees=employees, 
                         skills=skills, 
                         today=today,
                         current_employee_id=session.get('employee_id'),
                         is_admin=session.get('is_admin', False),
                         search_query=search_query)

@app.route('/project/add', methods=['POST'])
def add_project():
    try:
        name = request.form.get('name')
        if name:
            project = Project(name=name)
            db.session.add(project)
            db.session.commit()
            return {'success': True, 'id': project.id, 'name': project.name}
    except Exception as e:
        db.session.rollback()
        return {'success': False, 'error': str(e)}, 400
    return {'success': False, 'error': 'Invalid project name'}, 400

@app.route('/employee/add', methods=['GET', 'POST'])
def add_employee():
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            email = request.form.get('email')
            clock_id = request.form.get('clock_id')
            job_title = request.form.get('job_title')
            level_id = request.form.get('level_id')
            project_id = request.form.get('project_id')
            start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
            
            if name and email and job_title and level_id and start_date:
                employee = Employee(
                    name=name,
                    email=email,
                    clock_id=clock_id,
                    job_title=job_title,
                    level_id=level_id,
                    project_id=project_id if project_id else None,
                    start_date=start_date
                )
                db.session.add(employee)
                db.session.commit()
                flash('Employee added successfully!', 'success')
                return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding employee: {str(e)}', 'error')
    
    projects = Project.query.order_by(Project.name).all()
    levels = Level.query.order_by(Level.order).all()
    return render_template('add_employee.html', projects=projects, levels=levels)

@app.route('/skill/add', methods=['GET', 'POST'])
def add_skill():
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            description = request.form.get('description')
            requires_training = 'requires_training' in request.form
            training_expiry_months = request.form.get('training_expiry_months')
            training_details = request.form.get('training_details')
            
            if name:
                skill = Skill(
                    name=name,
                    description=description,
                    requires_training=requires_training,
                    training_expiry_months=training_expiry_months if training_expiry_months else None,
                    training_details=training_details
                )
                db.session.add(skill)
                db.session.commit()
                flash('Skill added successfully!', 'success')
                return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding skill: {str(e)}', 'error')
    
    return render_template('add_skill.html')

@app.route('/employee/<int:employee_id>/skills', methods=['GET', 'POST'])
@login_required
def update_employee_skills(employee_id):
    # Check if user is admin or updating their own skills
    if not session.get('is_admin', False) and session.get('employee_id') != employee_id:
        flash('You can only update your own skills.', 'error')
        return redirect(url_for('index'))
    
    employee = Employee.query.get_or_404(employee_id)
    skills = Skill.query.all()
    
    if request.method == 'POST':
        try:
            # Clear existing skills
            EmployeeSkill.query.filter_by(employee_id=employee_id).delete()
            
            # Add new skills
            for key, value in request.form.items():
                if key.startswith('skill_'):
                    skill_id = int(key.split('_')[1])
                    level = int(value)
                    
                    # Get training date if provided
                    training_date_key = f'training_date_{skill_id}'
                    training_date = request.form.get(training_date_key)
                    
                    skill = Skill.query.get(skill_id)
                    employee_skill = EmployeeSkill(
                        employee_id=employee_id,
                        skill_id=skill_id,
                        proficiency_level=level,
                        last_training_date=datetime.strptime(training_date, '%Y-%m-%d').date() if training_date else None
                    )
                    
                    # Calculate expiry date if applicable
                    if skill.requires_training and skill.training_expiry_months and training_date:
                        training_date_obj = datetime.strptime(training_date, '%Y-%m-%d').date()
                        expiry_date = datetime(
                            year=training_date_obj.year + ((training_date_obj.month + skill.training_expiry_months - 1) // 12),
                            month=((training_date_obj.month + skill.training_expiry_months - 1) % 12) + 1,
                            day=training_date_obj.day
                        ).date()
                        employee_skill.training_expiry_date = expiry_date
                    
                    db.session.add(employee_skill)
            
            db.session.commit()
            flash('Skills updated successfully!', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating skills: {str(e)}', 'error')
    
    return render_template('update_skills.html', 
                         employee=employee, 
                         skills=skills,
                         today=datetime.utcnow().date(),
                         is_admin=session.get('is_admin', False))

@app.route('/admin')
@admin_required
def admin():
    projects = Project.query.order_by(Project.name).all()
    levels = Level.query.order_by(Level.order).all()
    admins = Employee.query.filter_by(is_admin=True).order_by(Employee.name).all()
    
    # Get search queries and page numbers
    skill_search = request.args.get('skill_search', '').strip()
    employee_search = request.args.get('employee_search', '').strip()
    skill_page = request.args.get('skill_page', 1, type=int)
    employee_page = request.args.get('employee_page', 1, type=int)
    per_page = 10
    
    # Base query for skills
    skills_query = Skill.query
    
    # Apply skill search if query exists
    if skill_search:
        skills_query = skills_query.filter(
            or_(
                Skill.name.ilike(f'%{skill_search}%'),
                Skill.description.ilike(f'%{skill_search}%')
            )
        )
    
    # Base query for employees
    employees_query = Employee.query.filter_by(is_admin=False)  # Exclude admin users
    
    # Apply employee search if query exists
    if employee_search:
        employees_query = employees_query.join(Project, Employee.project_id == Project.id, isouter=True).filter(
            or_(
                Employee.name.ilike(f'%{employee_search}%'),
                Employee.email.ilike(f'%{employee_search}%'),
                Employee.job_title.ilike(f'%{employee_search}%'),
                Employee.clock_id.ilike(f'%{employee_search}%'),
                Project.name.ilike(f'%{employee_search}%')
            )
        )
    
    # Order and paginate
    skills_paginated = skills_query.order_by(Skill.name).paginate(
        page=skill_page, 
        per_page=per_page,
        error_out=False
    )
    
    employees_paginated = employees_query.order_by(Employee.name).paginate(
        page=employee_page,
        per_page=per_page,
        error_out=False
    )
    
    return render_template('admin.html',
                         projects=projects,
                         levels=levels,
                         skills=skills_paginated,
                         employees=employees_paginated,
                         admins=admins,
                         current_employee_id=session.get('employee_id'),
                         skill_search=skill_search,
                         employee_search=employee_search)

@app.route('/admin/project/add', methods=['POST'])
@admin_required
def admin_add_project():
    try:
        name = request.form.get('name')
        if name:
            project = Project(name=name)
            db.session.add(project)
            db.session.commit()
            flash('Project added successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding project: {str(e)}', 'error')
    return redirect(url_for('admin'))

@app.route('/admin/project/delete/<int:project_id>', methods=['POST'])
@admin_required
def admin_delete_project(project_id):
    try:
        project = Project.query.get_or_404(project_id)
        if not project.employees:  # Only delete if no employees are assigned
            db.session.delete(project)
            db.session.commit()
            flash('Project deleted successfully!', 'success')
        else:
            flash('Cannot delete project: Employees are still assigned to it', 'error')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting project: {str(e)}', 'error')
    return redirect(url_for('admin'))

@app.route('/admin/level/add', methods=['POST'])
@admin_required
def admin_add_level():
    try:
        name = request.form.get('name')
        order = request.form.get('order', type=int)
        if name and order is not None:
            level = Level(name=name, order=order)
            db.session.add(level)
            db.session.commit()
            flash('Level added successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding level: {str(e)}', 'error')
    return redirect(url_for('admin'))

@app.route('/admin/level/delete/<int:level_id>', methods=['POST'])
@admin_required
def admin_delete_level(level_id):
    try:
        level = Level.query.get_or_404(level_id)
        if not level.employees:  # Only delete if no employees are assigned
            db.session.delete(level)
            db.session.commit()
            flash('Level deleted successfully!', 'success')
        else:
            flash('Cannot delete level: Employees are still assigned to it', 'error')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting level: {str(e)}', 'error')
    return redirect(url_for('admin'))

@app.route('/admin/skill/add', methods=['POST'])
@admin_required
def admin_add_skill():
    try:
        name = request.form.get('name')
        description = request.form.get('description')
        requires_training = 'requires_training' in request.form
        training_expiry_months = request.form.get('training_expiry_months')
        training_details = request.form.get('training_details')
        
        if name:
            skill = Skill(
                name=name,
                description=description,
                requires_training=requires_training,
                training_expiry_months=training_expiry_months if training_expiry_months else None,
                training_details=training_details
            )
            db.session.add(skill)
            db.session.commit()
            flash('Skill added successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding skill: {str(e)}', 'error')
    return redirect(url_for('admin'))

@app.route('/admin/skill/edit/<int:skill_id>', methods=['POST'])
@admin_required
def admin_edit_skill(skill_id):
    try:
        skill = Skill.query.get_or_404(skill_id)
        
        skill.name = request.form.get('name')
        skill.description = request.form.get('description')
        skill.requires_training = 'requires_training' in request.form
        
        training_expiry_months = request.form.get('training_expiry_months')
        skill.training_expiry_months = training_expiry_months if training_expiry_months else None
        skill.training_details = request.form.get('training_details')
        
        db.session.commit()
        flash('Skill updated successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating skill: {str(e)}', 'error')
    return redirect(url_for('admin'))

@app.route('/admin/skill/delete/<int:skill_id>', methods=['POST'])
@admin_required
def admin_delete_skill(skill_id):
    try:
        skill = Skill.query.get_or_404(skill_id)
        if not skill.employee_skills:  # Only delete if no employees are using this skill
            db.session.delete(skill)
            db.session.commit()
            flash('Skill deleted successfully!', 'success')
        else:
            flash('Cannot delete skill: It is currently assigned to employees', 'error')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting skill: {str(e)}', 'error')
    return redirect(url_for('admin'))

@app.route('/employee/edit/<int:employee_id>', methods=['GET', 'POST'])
@admin_required
def edit_employee(employee_id):
    employee = Employee.query.get_or_404(employee_id)
    projects = Project.query.order_by(Project.name).all()
    levels = Level.query.order_by(Level.order).all()
    
    if request.method == 'POST':
        try:
            employee.name = request.form.get('name')
            employee.email = request.form.get('email')
            employee.clock_id = request.form.get('clock_id')
            employee.job_title = request.form.get('job_title')
            employee.level_id = request.form.get('level_id')
            employee.project_id = request.form.get('project_id') or None
            employee.start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
            
            db.session.commit()
            flash('Employee details updated successfully!', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating employee: {str(e)}', 'error')
    
    return render_template('edit_employee.html', 
                         employee=employee,
                         projects=projects,
                         levels=levels)

@app.route('/employee/report/<int:employee_id>')
@login_required
def employee_report(employee_id):
    # Get the employee with their skills and related data
    employee = Employee.query.options(
        joinedload(Employee.skills).joinedload(EmployeeSkill.skill),
        joinedload(Employee.level_rel),
        joinedload(Employee.project_rel)
    ).get_or_404(employee_id)
    
    # Get all available skills for comparison
    skills = Skill.query.all()
    
    # Check if the user has permission to view this report
    if not session.get('is_admin', False) and session.get('employee_id') != employee_id:
        flash('You do not have permission to view this report.', 'danger')
        return redirect(url_for('index'))
    
    return render_template('employee_report.html',
                         employee=employee,
                         skills=skills,
                         today=datetime.utcnow().date(),
                         is_admin=session.get('is_admin', False))

#------------------------------------------------------------------------------
# CLI Commands for User Management
#------------------------------------------------------------------------------

@app.cli.command("create-admin")
@click.argument('email')
@click.argument('name')
@click.argument('password')
def create_admin_command(email, name, password):
    """
    Create an administrator user with full system access.
    Required for initial system setup.
    """
    try:
        admin = Employee.query.filter_by(email=email).first()
        if admin:
            click.echo('Admin user already exists.')
            return

        admin = Employee(
            email=email,
            name=name,
            is_admin=True,
            job_title='Administrator',
            level_id=1,  # Default to first level
            start_date=datetime.utcnow().date()
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        click.echo('Admin user created successfully.')
    except Exception as e:
        db.session.rollback()
        click.echo(f'Error creating admin user: {str(e)}', err=True)

@app.route('/admin/admin-user/add', methods=['POST'])
@admin_required
def admin_add_admin():
    """Add a new admin user."""
    try:
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        job_title = request.form.get('job_title')
        level_id = request.form.get('level_id')
        
        if name and email and password and job_title and level_id:
            # Check if email already exists
            if Employee.query.filter_by(email=email).first():
                flash('Email already exists.', 'error')
                return redirect(url_for('admin'))
            
            # Create new admin user
            admin = Employee(
                name=name,
                email=email,
                job_title=job_title,
                level_id=level_id,
                is_admin=True,
                start_date=datetime.utcnow().date()
            )
            admin.set_password(password)
            
            db.session.add(admin)
            db.session.commit()
            flash('Admin user added successfully!', 'success')
        else:
            flash('All fields are required.', 'error')
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding admin user: {str(e)}', 'error')
    
    return redirect(url_for('admin'))

@app.route('/admin/admin-user/remove/<int:employee_id>', methods=['POST'])
@admin_required
def admin_remove_admin(employee_id):
    """Remove admin privileges from a user."""
    try:
        # Prevent removing own admin privileges
        if employee_id == session.get('employee_id'):
            flash('You cannot remove your own admin privileges.', 'error')
            return redirect(url_for('admin'))
        
        employee = Employee.query.get_or_404(employee_id)
        if employee.is_admin:
            employee.is_admin = False
            employee.password_hash = None  # Clear password hash as it's no longer needed
            db.session.commit()
            flash('Admin privileges removed successfully.', 'success')
        else:
            flash('User is not an admin.', 'error')
    except Exception as e:
        db.session.rollback()
        flash(f'Error removing admin privileges: {str(e)}', 'error')
    
    return redirect(url_for('admin'))

@app.route('/guide')
@login_required
def user_guide():
    """Display the user guide modal."""
    return redirect(url_for('index', _anchor='show-guide'))

@app.cli.command("init-data")
def init_data_command():
    """Initialize basic data required for the system (levels, etc.)"""
    try:
        # Check if we already have levels
        if Level.query.count() == 0:
            # Create default levels
            levels = [
                Level(name="Junior", order=1),
                Level(name="Mid-Level", order=2),
                Level(name="Senior", order=3),
                Level(name="Lead", order=4),
                Level(name="Principal", order=5)
            ]
            db.session.add_all(levels)
            click.echo('Created default levels')
        else:
            click.echo('Levels already exist, skipping...')

        # Check if we already have a default project
        if Project.query.count() == 0:
            # Create a default project
            default_project = Project(name="Unassigned")
            db.session.add(default_project)
            click.echo('Created default project')
        else:
            click.echo('Projects already exist, skipping...')

        db.session.commit()
        click.echo('Basic data initialization completed successfully')
        
    except Exception as e:
        db.session.rollback()
        click.echo(f'Error initializing data: {str(e)}', err=True)

@app.route('/admin/employee/delete/<int:employee_id>', methods=['POST'])
@admin_required
def admin_delete_employee(employee_id):
    """Delete an employee and their associated skills."""
    try:
        employee = Employee.query.get_or_404(employee_id)
        
        # Don't allow deleting admin users through this route
        if employee.is_admin:
            flash('Cannot delete admin users through this interface.', 'error')
            return redirect(url_for('admin'))
        
        # Delete associated skills first
        EmployeeSkill.query.filter_by(employee_id=employee_id).delete()
        
        # Delete the employee
        db.session.delete(employee)
        db.session.commit()
        flash('Employee deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting employee: {str(e)}', 'error')
    return redirect(url_for('admin'))

#------------------------------------------------------------------------------
# Application Entry Point
#------------------------------------------------------------------------------

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True) 