# Flask Skills Matrix Application
# This application manages employee skills, training, and professional development
# Author: [Your Name]
# Version: 1.0

# Standard library imports
from datetime import datetime, timedelta

# Third-party imports
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_file, after_this_request, Response
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import inspect, or_, desc
from sqlalchemy.orm import joinedload
from sqlalchemy.types import JSON # Import JSON type
import click
import io
import csv
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, EmailField, SubmitField, PasswordField, BooleanField, IntegerField, SelectField
from wtforms.validators import DataRequired, Length, Email, EqualTo, Optional, URL, NumberRange
from flask_migrate import Migrate

# Local application imports
from config import config
from database import db, init_db

# Initialize Flask application
app = Flask(__name__)
app.config.from_object(config)
init_db(app)
migrate = Migrate(app, db)

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
    about_me = db.Column(db.Text, nullable=True) # Added field for profile description
    phone_number = db.Column(db.String(20), nullable=True) # Added phone number field
    linkedin_url = db.Column(db.String(255), nullable=True) # Added LinkedIn URL field
    
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
    history_entries = db.relationship('EmployeeHistory', backref='employee_rel', lazy=True)

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
    training_category = db.Column(db.String(50), nullable=True) # e.g., 'External Formal', 'Internal Formal', 'Informal'
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
    notes = db.Column(db.Text)  # Personal notes/comments about the skill
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def calculate_and_set_expiry_date(self):
        """Calculates and sets the training expiry date based on the skill requirements."""
        # Ensure the related skill object is loaded
        if not self.skill:
            # This might happen if the object is not fully loaded, e.g., detached from session
            # You might need to handle this based on your application's logic,
            # perhaps by reloading or querying the skill explicitly if needed.
            # For now, we'll assume the skill relationship is usually available.
            # If you encounter issues, consider eager loading 'skill' where EmployeeSkill is queried.
            print(f"Warning: Skill relationship not loaded for EmployeeSkill ID {self.id}") # Added basic warning
            self.training_expiry_date = None
            return
        
        if self.skill.requires_training and self.skill.training_expiry_months and self.last_training_date:
            # Using a slightly more robust way to calculate expiry date
            # This handles month rollovers correctly
            year = self.last_training_date.year + (self.last_training_date.month + self.skill.training_expiry_months - 1) // 12
            month = (self.last_training_date.month + self.skill.training_expiry_months - 1) % 12 + 1
            day = self.last_training_date.day
            # Handle cases like adding months to Jan 31st resulting in an invalid date like Feb 31st
            try:
                self.training_expiry_date = datetime(year, month, day).date()
            except ValueError:
                # If the day is invalid for the calculated month (e.g., Feb 30th),
                # set it to the last valid day of that month.
                # Find the first day of the next month and subtract one day.
                next_month_year = year + (month // 12)
                next_month_month = (month % 12) + 1
                last_day_of_month = datetime(next_month_year, next_month_month, 1).date() - timedelta(days=1)
                self.training_expiry_date = last_day_of_month
        else:
            self.training_expiry_date = None # Ensure expiry date is None if conditions aren't met

# New model for employee job history
class EmployeeHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False, index=True)
    job_title = db.Column(db.String(100), nullable=False)
    level_id = db.Column(db.Integer, db.ForeignKey('level.id'), nullable=False, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=True, index=True)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=True)
    change_reason = db.Column(db.String(255), nullable=True)
    notes = db.Column(db.Text, nullable=True) # New field for admin notes
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships for easier access in templates if needed (optional here)
    level_rel = db.relationship('Level', lazy='joined')
    project_rel = db.relationship('Project', lazy='joined')

class ProfileForm(FlaskForm):
    """Form for users to edit their profile information."""
    username = StringField('Username', render_kw={'readonly': True})
    job_title = StringField('Job Title', render_kw={'readonly': True})
    level_name = StringField('Level', render_kw={'readonly': True})
    project_name = StringField('Project', render_kw={'readonly': True})
    start_date_str = StringField('Start Date', render_kw={'readonly': True})
    email = EmailField('Email', validators=[DataRequired(), Email()])
    phone_number = StringField('Phone Number', validators=[Length(min=0, max=20)])
    linkedin_url = StringField('LinkedIn Profile URL', validators=[Optional(), URL(), Length(max=255)])
    about_me = TextAreaField('About Me', validators=[Length(min=0, max=500)])
    submit = SubmitField('Update Profile')

# Form for adding/editing skills
class SkillForm(FlaskForm):
    name = StringField('Skill Name', validators=[DataRequired(), Length(max=100)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=1000)])
    training_category = SelectField('Training Category',
                                  choices=[
                                      ('', 'Select Category...'),
                                      ('Formal External', 'Formal External'),
                                      ('Formal Internal', 'Formal Internal'),
                                      ('Informal', 'Informal/On-the-Job')
                                  ], validators=[Optional()])
    requires_training = BooleanField('Requires Formal Training')
    training_expiry_months = IntegerField('Validity Period (months)',
                                        validators=[Optional(), NumberRange(min=1)])
    training_details = TextAreaField('Training Requirements', validators=[Optional(), Length(max=1000)])
    submit = SubmitField('Save Skill')

# Model for Audit Trail
class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=True) # Nullable for system actions
    user_email = db.Column(db.String(120), nullable=True) # Store email for easier viewing
    action = db.Column(db.String(255), nullable=False, index=True)
    target_type = db.Column(db.String(50), nullable=True, index=True)
    target_id = db.Column(db.Integer, nullable=True)
    details = db.Column(JSON, nullable=True) # Store additional info like changes

    user = db.relationship('Employee') # Relationship to Employee

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
            session['user_name'] = employee.name # Store user name
            session['is_admin'] = True
            log_audit(action="Admin Login Success", user_id=employee.id, user_email=employee.email)
            db.session.commit() # Commit log entry
            flash('Logged in successfully as administrator.', 'success')
            return redirect(url_for('admin'))
        elif employee and employee.clock_id == identifier:
            # Regular employee login - only requires clock ID
            session.permanent = remember  # Make session permanent if remember is checked
            session['employee_id'] = employee.id
            session['user_name'] = employee.name # Store user name
            session['is_admin'] = False
            log_audit(action="User Login Success", user_id=employee.id, user_email=employee.email)
            db.session.commit() # Commit log entry
            flash('Logged in successfully.', 'success')
            return redirect(url_for('index'))
        else:
            # Log failed login attempt
            log_audit(action="Login Failed", details={'identifier': identifier})
            db.session.commit() # Commit log entry
            flash('Invalid credentials.', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Clear user session and redirect to login page."""
    user_id = session.get('employee_id') # Get user ID before clearing
    user_email = session.get('user_name') # Assuming user_name holds email, adjust if needed
    log_audit(action="User Logout", user_id=user_id, user_email=user_email) # Log before clearing
    session.clear()
    db.session.commit() # Commit log entry after clearing session (might be safer)
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
# Helper Functions
#------------------------------------------------------------------------------

def log_audit(action, target_type=None, target_id=None, details=None):
    """Helper function to log an audit trail entry."""
    user_id = session.get('employee_id')
    user_email = None
    if user_id:
        # Querying the user just for the email might be slightly inefficient.
        # Consider storing email in session if performance becomes an issue.
        user = Employee.query.get(user_id)
        if user:
            user_email = user.email
    
    log_entry = AuditLog(
        user_id=user_id,
        user_email=user_email,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details
    )
    db.session.add(log_entry)
    # Note: The commit happens in the route where this is called.

def _get_filtered_employees_query(search_query, filter_skill_id, filter_min_proficiency):
    """Builds the base query for employees with optional filtering."""
    # Start with base query, excluding admins from general lists
    query = Employee.query.filter(Employee.is_admin == False)

    # Apply search if query exists
    if search_query:
        search = f"%{search_query}%"
        # Use outerjoin for Project to include employees without projects
        query = query.outerjoin(Project, Employee.project_id == Project.id).filter(
            db.or_(
                Employee.name.ilike(search),
                Employee.job_title.ilike(search),
                Employee.email.ilike(search),
                Employee.clock_id.ilike(search), # Added clock_id to search
                Project.name.ilike(search) # Search by project name
            )
        )

    # Apply skill filter if provided
    if filter_skill_id:
        # Join with EmployeeSkill
        query = query.join(EmployeeSkill).filter(
            EmployeeSkill.skill_id == filter_skill_id
        )
        # Apply minimum proficiency if specified
        if filter_min_proficiency:
            valid_proficiency = max(1, min(filter_min_proficiency, 5))
            query = query.filter(EmployeeSkill.proficiency_level >= valid_proficiency)
        
        # Group by Employee fields to avoid duplicates if an employee has the skill multiple times (though unlikely with current structure)
        # Or simply ensure distinct employees if joins cause duplicates
        # Using distinct() is often simpler than group_by for this purpose if supported by the join strategy
        query = query.distinct(Employee.id) # Use distinct instead of group_by

    # Eager load relationships AFTER joins and filters but BEFORE ordering/pagination
    # Load only what's needed for list display or export
    query = query.options(
        joinedload(Employee.level_rel),
        joinedload(Employee.project_rel),
        # Eager load skills only if needed for display/export logic later
        # For basic export, we might not need this, improving performance
        # joinedload(Employee.skills).joinedload(EmployeeSkill.skill) 
    )
    return query

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
    Supports filtering by skill and minimum proficiency.
    Uses pagination for the employee list if viewed by an admin.
    """
    # Get search, filter, and page parameters
    search_query = request.args.get('search', '').strip()
    filter_skill_id = request.args.get('skill_id', type=int)
    default_proficiency = 1 if filter_skill_id else None 
    filter_min_proficiency = request.args.get('min_proficiency', default=default_proficiency, type=int)
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    all_skills = Skill.query.order_by(Skill.name).all()
    today = datetime.utcnow().date()

    if session.get('is_admin', False):
        # --- Admin View Logic --- 
        query = _get_filtered_employees_query(search_query, filter_skill_id, filter_min_proficiency)
        
        # Eager load skills data needed for the main table display
        query = query.options(joinedload(Employee.skills).joinedload(EmployeeSkill.skill))

        pagination = query.order_by(Employee.name).paginate(
            page=page, 
            per_page=per_page, 
            error_out=False
        )
        employees_paginated = pagination.items
        
        return render_template('index.html', 
                             employees=employees_paginated,
                             skills=all_skills,
                             today=today,
                             current_employee_id=session.get('employee_id'),
                             is_admin=True,
                             search_query=search_query,
                             filter_skill_id=filter_skill_id,
                             filter_min_proficiency=filter_min_proficiency,
                             pagination=pagination)
    else:
        # --- Non-Admin View Logic --- 
        employee = Employee.query.options(
            joinedload(Employee.skills).joinedload(EmployeeSkill.skill),
            joinedload(Employee.level_rel),
            joinedload(Employee.project_rel)
        ).filter_by(id=session.get('employee_id')).first_or_404()
        
        return render_template('index.html', 
                             employees=[employee],
                             skills=all_skills, 
                             today=today,
                             current_employee_id=session.get('employee_id'),
                             is_admin=False,
                             search_query='', # No search/filter for single user
                             filter_skill_id=None,
                             filter_min_proficiency=None,
                             pagination=None)

@app.route('/project/add', methods=['POST'])
def add_project():
    try:
        name = request.form.get('name')
        if name:
            project = Project(name=name)
            db.session.add(project)
            db.session.commit()
            log_audit(action="Project Added", target_type="Project", target_id=project.id, details={'name': name})
            db.session.commit()
            flash('Project added successfully!', 'success')
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
                # Flush to get the employee.id before creating history
                db.session.flush()
                
                # Create initial history entry
                initial_history = EmployeeHistory(
                    employee_id=employee.id,
                    job_title=employee.job_title,
                    level_id=employee.level_id,
                    project_id=employee.project_id,
                    start_date=employee.start_date,
                    end_date=None,
                    change_reason="Initial Hire"
                )
                db.session.add(initial_history)
                
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
                log_audit(action="Skill Added", target_type="Skill", target_id=skill.id, details={'name': skill.name})
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

    # Eager load skills and the related skill object for efficiency
    employee = Employee.query.options(
        joinedload(Employee.skills).joinedload(EmployeeSkill.skill)
    ).get_or_404(employee_id)
    all_skills = Skill.query.order_by(Skill.name).all() # Fetch all possible skills for the form

    if request.method == 'POST':
        # Dictionary to store changes for logging
        log_details = {
            'skills_added': [],
            'skills_updated': [],
            'skills_removed': [] # This will be populated later
        }
        try:
            # Get existing skills for this employee, keyed by skill_id
            existing_employee_skills = {es.skill_id: es for es in employee.skills}
            submitted_skill_ids = set()

            # Process form data - iterate through all possible skills to handle checkboxes/radios correctly
            for skill in all_skills:
                skill_id = skill.id
                level_str = request.form.get(f'skill_{skill_id}')

                if level_str: # Skill was submitted (level selected)
                    submitted_skill_ids.add(skill_id)
                    level = int(level_str)

                    # Get training date and notes if provided
                    training_date_str = request.form.get(f'training_date_{skill_id}')
                    notes = request.form.get(f'notes_{skill_id}', '').strip()
                    last_training_date = None
                    if training_date_str:
                        try:
                            last_training_date = datetime.strptime(training_date_str, '%Y-%m-%d').date()
                        except ValueError:
                            flash(f"Invalid date format for skill '{skill.name}'. Please use YYYY-MM-DD.", 'error')
                            # Optionally, you could skip this skill or handle the error differently
                            continue # Skip this skill update if date is invalid


                if skill_id in existing_employee_skills:
                    # Update existing skill
                    employee_skill = existing_employee_skills[skill_id]
                    # Capture original state for logging changes
                    original_level = employee_skill.proficiency_level
                    original_date = employee_skill.last_training_date
                    original_notes = employee_skill.notes if employee_skill.notes else ''
                    
                    needs_update = False
                    change_info = {}
                    if employee_skill.proficiency_level != level:
                        change_info['proficiency'] = {'old': original_level, 'new': level}
                        employee_skill.proficiency_level = level
                        needs_update = True
                    if employee_skill.last_training_date != last_training_date:
                         change_info['training_date'] = {'old': str(original_date) if original_date else None, 'new': str(last_training_date) if last_training_date else None}
                         employee_skill.last_training_date = last_training_date
                         needs_update = True
                    submitted_notes = notes if notes else ''
                    if original_notes != submitted_notes:
                         change_info['notes'] = {'old': original_notes, 'new': submitted_notes}
                         employee_skill.notes = notes if notes else None
                         needs_update = True

                    if needs_update:
                        employee_skill.calculate_and_set_expiry_date()
                        db.session.add(employee_skill)
                        log_details['skills_updated'].append({'name': skill.name, **change_info}) # Log specific changes

                else:
                    # Add new skill
                    # Skill object is already available from the 'all_skills' loop
                    employee_skill = EmployeeSkill(
                        employee_id=employee_id,
                        skill_id=skill_id,
                        proficiency_level=level,
                        last_training_date=last_training_date,
                        notes=notes if notes else None,
                        skill=skill # Associate the skill object directly
                    )
                    employee_skill.calculate_and_set_expiry_date() # Calculate expiry
                    db.session.add(employee_skill)
                    log_details['skills_added'].append({
                        'name': skill.name, 
                        'level': level, 
                        'date': str(last_training_date) if last_training_date else None,
                        'notes': notes if notes else None
                    })

            # Delete skills that were previously assigned but not in the form submission
            skill_ids_to_delete = set(existing_employee_skills.keys()) - submitted_skill_ids
            if skill_ids_to_delete:
                log_details['skills_removed'] = [s.name for s in Skill.query.filter(Skill.id.in_(skill_ids_to_delete)).all()]
            for skill_id in skill_ids_to_delete:
                skill_to_delete = existing_employee_skills[skill_id]
                db.session.delete(skill_to_delete)

            db.session.commit()
            log_audit(action="Employee Skills Updated", target_type="Employee", target_id=employee_id, details=log_details)
            db.session.commit()
            flash('Skills updated successfully!', 'success')
            # Redirect to the employee's report page for better UX
            return redirect(url_for('employee_report', employee_id=employee_id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating skills: {str(e)}', 'error')
            # Re-fetch employee data in case of error to render form correctly
            employee = Employee.query.options(
                joinedload(Employee.skills).joinedload(EmployeeSkill.skill)
            ).get_or_404(employee_id)


    # GET request or after error
    return render_template('update_skills.html',
                         employee=employee,
                         skills=all_skills, # Pass all skills to the template
                         today=datetime.utcnow().date(),
                         is_admin=session.get('is_admin', False))

@app.route('/admin')
@admin_required
def admin():
    projects = Project.query.order_by(Project.name).all()
    levels = Level.query.order_by(Level.order).all()
    admins = Employee.query.filter_by(is_admin=True).order_by(Employee.name).all()
    
    skill_search = request.args.get('skill_search', '').strip()
    employee_search = request.args.get('employee_search', '').strip() # This is the employee search for the admin employee table
    skill_page = request.args.get('skill_page', 1, type=int)
    employee_page = request.args.get('employee_page', 1, type=int)
    per_page = 10
    
    # Skills Query (remains the same)
    skills_query = Skill.query
    if skill_search:
        skills_query = skills_query.filter(Skill.name.ilike(f'%{skill_search}%'))
    skills_pagination = skills_query.order_by(Skill.name).paginate(page=skill_page, per_page=10, error_out=False)
    
    add_skill_form = SkillForm() # Form for adding skills
    edit_skill_form = SkillForm() # Form for editing skills (will be populated by JS)
    
    # Use helper for Employee Query (no skill filter needed here, just search)
    # Pass None for skill filters to the helper
    employees_query = _get_filtered_employees_query(employee_search, None, None)
    
    # Eager load skills data needed for the admin employee table display (if any)
    # If the admin employee table doesn't show skill details, remove this.
    # employees_query = employees_query.options(joinedload(Employee.skills).joinedload(EmployeeSkill.skill)) 

    employees_paginated = employees_query.order_by(Employee.name).paginate(
        page=employee_page,
        per_page=per_page,
        error_out=False
    )
    
    return render_template('admin.html',
                         projects=projects,
                         levels=levels,
                         skills=skills_pagination,
                         employees=employees_paginated,
                         admins=admins,
                         current_employee_id=session.get('employee_id'),
                         skill_search=skill_search,
                         employee_search=employee_search,
                         add_skill_form=add_skill_form,
                         edit_skill_form=edit_skill_form)

@app.route('/admin/project/add', methods=['POST'])
@admin_required
def admin_add_project():
    try:
        name = request.form.get('name')
        if name:
            project = Project(name=name)
            db.session.add(project)
            db.session.commit()
            log_audit(action="Project Added", target_type="Project", target_id=project.id, details={'name': name})
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
            project_name = project.name # Get name before deletion
            db.session.delete(project)
            db.session.commit()
            log_audit(action="Project Deleted", target_type="Project", target_id=project_id, details={'name': project_name})
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
            log_audit(action="Level Added", target_type="Level", target_id=level.id, details={'name': name, 'order': order})
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
            level_name = level.name # Get name before deletion
            db.session.delete(level)
            db.session.commit()
            log_audit(action="Level Deleted", target_type="Level", target_id=level_id, details={'name': level_name})
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
    """Handles adding a new skill via the admin panel using WTForms."""
    form = SkillForm()
    if form.validate_on_submit():
        try:
            # Check if skill name already exists
            existing_skill = Skill.query.filter(Skill.name.ilike(form.name.data)).first()
            if existing_skill:
                flash(f'Skill "{form.name.data}" already exists.', 'warning')
            else:
                skill = Skill(
                    name=form.name.data,
                    description=form.description.data,
                    training_category=form.training_category.data or None,
                    requires_training=form.requires_training.data,
                    training_expiry_months=form.training_expiry_months.data if form.requires_training.data else None,
                    training_details=form.training_details.data if form.requires_training.data else None
                )
                db.session.add(skill)
                db.session.commit()
                log_audit(action="Skill Added", target_type="Skill", target_id=skill.id, details={'name': skill.name})
                db.session.commit()
                flash('Skill added successfully!', 'success')
                return redirect(url_for('admin')) # Redirect to clear form
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding skill: {str(e)}', 'error')
    else:
        # Handle validation errors - flash messages
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Error in {getattr(form, field).label.text}: {error}", 'error')
                
    # Redirect back to admin page (usually to the skills tab) even on error
    # You might want to add logic to re-open the correct tab
    return redirect(url_for('admin')) # Consider redirecting with anchor #skills-management

@app.route('/admin/skill/edit/<int:skill_id>', methods=['POST'])
@admin_required
def admin_edit_skill(skill_id):
    """Handles editing an existing skill via the admin panel using WTForms."""
    skill = Skill.query.get_or_404(skill_id)
    # Capture original data before form processing
    original_data = {
        'name': skill.name,
        'description': skill.description,
        'training_category': skill.training_category,
        'requires_training': skill.requires_training,
        'training_expiry_months': skill.training_expiry_months,
        'training_details': skill.training_details
    }
    form = SkillForm(obj=skill) # Pre-populate form with existing skill data
    
    if form.validate_on_submit():
        try:
            # Check if name is being changed to one that already exists
            new_name = form.name.data
            if new_name.lower() != skill.name.lower(): # Case-insensitive check
                existing_skill = Skill.query.filter(Skill.name.ilike(new_name), Skill.id != skill_id).first()
                if existing_skill:
                    flash(f'Skill name "{new_name}" already exists.', 'warning')
                    # Need to re-render or handle this without losing edits - JS approach is better here
                    # For simplicity now, just redirecting back might lose edits.
                    return redirect(url_for('admin')) 
            
            # Update skill object from form data
            skill.name = new_name
            skill.description = form.description.data
            skill.training_category = form.training_category.data or None
            skill.requires_training = form.requires_training.data
            skill.training_expiry_months = form.training_expiry_months.data if skill.requires_training else None
            skill.training_details = form.training_details.data if skill.requires_training else None
            
            db.session.commit()
            # Log changes
            changes = {}
            if skill.name != original_data['name']: changes['name'] = {'old': original_data['name'], 'new': skill.name}
            if skill.description != original_data['description']: changes['description'] = {'old': original_data['description'], 'new': skill.description}
            if skill.training_category != original_data['training_category']: changes['training_category'] = {'old': original_data['training_category'], 'new': skill.training_category}
            if skill.requires_training != original_data['requires_training']: changes['requires_training'] = {'old': original_data['requires_training'], 'new': skill.requires_training}
            if skill.training_expiry_months != original_data['training_expiry_months']: changes['training_expiry_months'] = {'old': original_data['training_expiry_months'], 'new': skill.training_expiry_months}
            if skill.training_details != original_data['training_details']: changes['training_details'] = {'old': original_data['training_details'], 'new': skill.training_details}

            log_audit(action="Skill Edited", target_type="Skill", target_id=skill_id, details=changes if changes else None)
            db.session.commit()
            flash('Skill updated successfully!', 'success')
            return redirect(url_for('admin')) # Redirect to clear form
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating skill: {str(e)}', 'error')
    else:
        # Handle validation errors
        for field, errors in form.errors.items():
            for error in errors:
                 flash(f"Error in {getattr(form, field).label.text}: {error}", 'error')
                 
    # Redirect back to admin page (usually to the skills tab) even on error
    return redirect(url_for('admin')) # Consider redirecting with anchor #skills-management

@app.route('/admin/skill/delete/<int:skill_id>', methods=['POST'])
@admin_required
def admin_delete_skill(skill_id):
    try:
        skill = Skill.query.get_or_404(skill_id)
        if not skill.employee_skills:  # Only delete if no employees are using this skill
            skill_name = skill.name # Get name before deletion
            db.session.delete(skill)
            db.session.commit()
            log_audit(action="Skill Deleted", target_type="Skill", target_id=skill_id, details={'name': skill_name})
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
    # Capture relevant original data
    original_data = {
        'name': employee.name,
        'email': employee.email,
        'clock_id': employee.clock_id,
        'job_title': employee.job_title,
        'level_id': employee.level_id,
        'project_id': employee.project_id,
        'start_date': employee.start_date.isoformat() if employee.start_date else None
    }
    projects = Project.query.order_by(Project.name).all()
    levels = Level.query.order_by(Level.order).all()
    
    if request.method == 'POST':
        try:
            # Get original values before modification for comparison
            original_job_title = employee.job_title
            original_level_id = employee.level_id
            original_project_id = employee.project_id
            
            # Update employee attributes from form
            employee.name = request.form.get('name')
            employee.email = request.form.get('email')
            employee.clock_id = request.form.get('clock_id')
            new_job_title = request.form.get('job_title')
            new_level_id = int(request.form.get('level_id')) # Convert to int
            new_project_id_str = request.form.get('project_id')
            new_project_id = int(new_project_id_str) if new_project_id_str else None
            new_start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
            change_notes = request.form.get('change_notes', '').strip() # Get change notes
            new_role_start_date_str = request.form.get('new_role_start_date')
            
            
            # Check if role-related info changed
            role_changed = (
                new_job_title != original_job_title or \
                new_level_id != original_level_id or \
                new_project_id != original_project_id
            )
            
            # Apply changes to the employee object
            employee.job_title = new_job_title
            employee.level_id = new_level_id
            employee.project_id = new_project_id
            employee.start_date = new_start_date # Update overall company start date if explicitly changed
            
            if role_changed:
                # Parse and validate the new role start date
                try:
                    new_role_start = datetime.strptime(new_role_start_date_str, '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    flash('Invalid date format for New Role Start Date. Please use YYYY-MM-DD.', 'error')
                    # Re-render form without committing changes
                    today_date_str = datetime.utcnow().date().strftime('%Y-%m-%d')
                    return render_template('edit_employee.html', 
                                         employee=employee, 
                                         projects=projects, 
                                         levels=levels, 
                                         today_date_str=today_date_str)
                
                # Determine the reason for change
                change_reason = []
                if new_job_title != original_job_title: change_reason.append("Job Title Change")
                if new_level_id != original_level_id:
                    # Basic promotion/demotion logic based on level order
                    original_level = Level.query.get(original_level_id)
                    new_level = Level.query.get(new_level_id)
                    if original_level and new_level:
                         if new_level.order > original_level.order: change_reason.append("Promotion")
                         elif new_level.order < original_level.order: change_reason.append("Demotion")
                         else: change_reason.append("Level Change (Same Order)") # Or handle as needed
                    else: change_reason.append("Level Change") # Fallback
                if new_project_id != original_project_id: change_reason.append("Project Change")
                final_reason = ", ".join(change_reason) if change_reason else "Update"
                
                # Find current history record and end it
                current_history = EmployeeHistory.query.filter_by(
                    employee_id=employee.id, 
                    end_date=None
                ).order_by(desc(EmployeeHistory.start_date)).first()
                
                if current_history:
                    # Validate new_role_start is not before current_history start
                    if new_role_start <= current_history.start_date:
                       flash(f'New role start date ({new_role_start.strftime("%Y-%m-%d")}) cannot be on or before the previous role start date ({current_history.start_date.strftime("%Y-%m-%d")}).', 'error')
                       today_date_str = datetime.utcnow().date().strftime('%Y-%m-%d')
                       return render_template('edit_employee.html', employee=employee, projects=projects, levels=levels, today_date_str=today_date_str)
                       
                    current_history.end_date = new_role_start - timedelta(days=1) # End previous record the day before
                    db.session.add(current_history)
                
                # Create new history record
                new_history = EmployeeHistory(
                    employee_id=employee.id,
                    job_title=new_job_title,
                    level_id=new_level_id,
                    project_id=new_project_id,
                    start_date=new_role_start, # Use the provided start date
                    end_date=None,
                    change_reason=final_reason,
                    notes=change_notes if change_notes else None # Save notes
                )
                db.session.add(new_history)

            db.session.commit()
            # Log changes
            changes = {}
            if employee.name != original_data['name']: changes['name'] = {'old': original_data['name'], 'new': employee.name}
            if employee.email != original_data['email']: changes['email'] = {'old': original_data['email'], 'new': employee.email}
            if employee.clock_id != original_data['clock_id']: changes['clock_id'] = {'old': original_data['clock_id'], 'new': employee.clock_id}
            if employee.job_title != original_data['job_title']: changes['job_title'] = {'old': original_data['job_title'], 'new': employee.job_title}
            if employee.level_id != original_data['level_id']: changes['level_id'] = {'old': original_data['level_id'], 'new': employee.level_id}
            if employee.project_id != original_data['project_id']: changes['project_id'] = {'old': original_data['project_id'], 'new': employee.project_id}
            new_start_date_iso = employee.start_date.isoformat() if employee.start_date else None
            if new_start_date_iso != original_data['start_date']: changes['start_date'] = {'old': original_data['start_date'], 'new': new_start_date_iso}
            
            log_audit(action="Employee Edited", target_type="Employee", target_id=employee_id, details=changes if changes else {'note': 'No base details changed'})
            db.session.commit()
            flash('Employee details updated successfully!', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating employee: {str(e)}', 'error')
    
    # GET request or if POST failed
    today_date_str = datetime.utcnow().date().strftime('%Y-%m-%d')
    return render_template('edit_employee.html', 
                         employee=employee,
                         projects=projects,
                         levels=levels,
                         today_date_str=today_date_str) # Pass today's date for default

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
    
    # Get employee history, ordered by start date descending
    # Eager load level and project relationships for efficiency
    history = EmployeeHistory.query.filter_by(employee_id=employee_id)\
                                 .options(joinedload(EmployeeHistory.level_rel), joinedload(EmployeeHistory.project_rel))\
                                 .order_by(desc(EmployeeHistory.start_date)).all()
    
    # Check if the user has permission to view this report
    if not session.get('is_admin', False) and session.get('employee_id') != employee_id:
        flash('You do not have permission to view this report.', 'danger')
        return redirect(url_for('index'))
    
    return render_template('employee_report.html',
                         employee=employee,
                         skills=skills,
                         today=datetime.utcnow().date(),
                         history=history, # Pass history to template
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
        # Check if level 1 exists, create if not
        level1 = Level.query.filter_by(order=1).first()
        if not level1:
            level1 = Level(name="Default Admin Level", order=1)
            db.session.add(level1)
            db.session.flush() # Get ID
            click.echo('Created default Level 1 for admin user.')
        level_id_to_use = level1.id
            
        admin = Employee.query.filter_by(email=email).first()
        if admin:
            click.echo('Admin user already exists.')
            return

        admin = Employee(
            email=email,
            name=name,
            is_admin=True,
            job_title='Administrator',
            level_id=level_id_to_use,  # Use found/created level 1
            start_date=datetime.utcnow().date()
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        log_audit(action="Admin Created (CLI)", target_type="Employee", target_id=admin.id, details={'email': email, 'name': name})
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
            log_audit(action="Admin Added (UI)", target_type="Employee", target_id=admin.id, details={'email': email, 'name': name})
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
            employee_email = employee.email # Get email before change
            employee.is_admin = False
            employee.password_hash = None  # Clear password hash as it's no longer needed
            db.session.commit()
            log_audit(action="Admin Privileges Removed", target_type="Employee", target_id=employee_id, details={'email': employee_email})
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
                Level(name="Placement", order=1),
                Level(name="Apprentice", order=2),
                Level(name="Graduate", order=3),
                Level(name="Senior Engineer", order=4),
                Level(name="Principal Engineer", order=5),
                Level(name="Senior Principal Engineer", order=6),
                Level(name="Chief", order=7),
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
        
        employee_name = employee.name # Get name before deletion
        employee_email = employee.email # Get email before deletion
        # Delete associated skills first
        EmployeeSkill.query.filter_by(employee_id=employee_id).delete()
        
        # Delete the employee
        db.session.delete(employee)
        db.session.commit()
        log_audit(action="Employee Deleted", target_type="Employee", target_id=employee_id, details={'name': employee_name, 'email': employee_email})
        db.session.commit()
        flash('Employee deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting employee: {str(e)}', 'error')
    return redirect(url_for('admin'))

@app.route('/admin/database/backup')
@admin_required
def backup_database():
    """Create a backup of the database in SQLite format."""
    backup_db_path = None # Initialize path variable
    try:
        # Create a temporary SQLite database
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        # Ensure a unique temporary filename
        import tempfile, os
        temp_dir = tempfile.gettempdir()
        backup_db_path = os.path.join(temp_dir, f'backup_skills_matrix_{timestamp}.db')
        backup_uri = f'sqlite:///{backup_db_path}'
        
        # Create engine for backup database
        # Use create_engine directly from sqlalchemy for temporary engine
        from sqlalchemy import create_engine 
        backup_engine = create_engine(backup_uri)
        
        # Create all tables in the backup database
        db.Model.metadata.create_all(backup_engine)
        
        # Create a new session for the backup database
        from sqlalchemy.orm import sessionmaker
        BackupSession = sessionmaker(bind=backup_engine)
        backup_session = BackupSession()
        
        # Get all models from the current database
        # Ensure correct order if there are dependencies not handled by relationships
        models = [Level, Project, Employee, Skill, EmployeeSkill] 
        
        # Copy data from each model
        for model in models:
            # Get all records from the current database using the app's session
            with app.app_context(): 
                records = db.session.query(model).all()
            
            # Insert records into backup database
            for record in records:
                # Create a new instance without SQLAlchemy's instrumentation
                # Detach the instance from the original session if necessary (usually not needed for .all())
                backup_record_data = {c.name: getattr(record, c.name) for c in model.__table__.columns}
                backup_record = model(**backup_record_data)
                
                backup_session.add(backup_record)
        
        # Commit the backup
        backup_session.commit()
        backup_session.close()
        
        # Send the file
        from flask import send_file
        
        # Generate filename with timestamp
        download_name = f'skills_matrix_backup_{timestamp}.db'
        
        # Use after_this_request correctly within the try block where the file is created
        @after_this_request
        def remove_file(response):
            if backup_db_path and os.path.exists(backup_db_path):
                try:
                    os.remove(backup_db_path)
                    app.logger.info(f"Successfully removed temporary backup file: {backup_db_path}")
                except Exception as error_remove:
                    app.logger.error(f"Error removing temporary backup file {backup_db_path}: {error_remove}")
            return response

        return send_file(
            backup_db_path,
            mimetype='application/x-sqlite3',
            as_attachment=True,
            download_name=download_name
        )
        
    except Exception as e:
        # Log the full error for debugging
        app.logger.error(f"Error creating backup: {str(e)}", exc_info=True)
        flash(f'Error creating backup: An internal error occurred. Check logs.', 'error')
        # Clean up potentially created file on error before redirect
        if backup_db_path and os.path.exists(backup_db_path):
             try:
                 os.remove(backup_db_path)
             except Exception as error_remove_fail:
                 app.logger.error(f"Error removing backup file after failure {backup_db_path}: {error_remove_fail}")
        return redirect(url_for('admin'))

@app.route('/admin/database/restore', methods=['POST'])
@admin_required
def restore_database():
    """Restore the database from a SQLite backup file."""
    try:
        if 'backup_file' not in request.files:
            flash('No backup file provided', 'error')
            return redirect(url_for('admin'))
        
        file = request.files['backup_file']
        if file.filename == '':
            flash('No backup file selected', 'error')
            return redirect(url_for('admin'))
        
        if not file.filename.endswith('.db'):
            flash('Invalid file type. Please upload a .db file', 'error')
            return redirect(url_for('admin'))
        
        # Save the uploaded file temporarily
        import tempfile
        import os
        
        temp_dir = tempfile.mkdtemp()
        backup_path = os.path.join(temp_dir, 'temp_backup.db')
        file.save(backup_path)
        
        try:
            # Create engine for the backup database
            backup_uri = f'sqlite:///{backup_path}'
            backup_engine = db.create_engine(backup_uri)
            
            # Verify this is a valid backup by checking for required tables
            from sqlalchemy import inspect
            inspector = inspect(backup_engine)
            required_tables = {'employee', 'level', 'project', 'skill', 'employee_skill'}
            existing_tables = set(inspector.get_table_names())
            
            if not required_tables.issubset(existing_tables):
                raise ValueError('Invalid backup file: Missing required tables')
            
            # Create a session for the backup database
            from sqlalchemy.orm import sessionmaker
            BackupSession = sessionmaker(bind=backup_engine)
            backup_session = BackupSession()
            
            # Clear existing data
            EmployeeSkill.query.delete()
            Employee.query.delete()
            Skill.query.delete()
            Project.query.delete()
            Level.query.delete()
            
            # Models in order of restoration (respecting foreign key constraints)
            models = [Level, Project, Employee, Skill, EmployeeSkill]
            
            # Restore data from backup
            for model in models:
                # Get records from backup
                backup_records = backup_session.query(model).all()
                
                # Insert into current database
                for record in backup_records:
                    new_record = model()
                    for column in model.__table__.columns:
                        setattr(new_record, column.name, getattr(record, column.name))
                    db.session.add(new_record)
            
            db.session.commit()
            backup_session.close()
            flash('Database restored successfully!', 'success')
            
        finally:
            # Clean up temporary files
            import shutil
            shutil.rmtree(temp_dir)
        
        return redirect(url_for('admin'))
        
    except ValueError as e:
        db.session.rollback()
        flash(str(e), 'error')
        return redirect(url_for('admin'))
    except Exception as e:
        db.session.rollback()
        flash(f'Error restoring database: {str(e)}', 'error')
        return redirect(url_for('admin'))

#------------------------------------------------------------------------------
# Export Routes
#------------------------------------------------------------------------------

@app.route('/export/employees')
@login_required
@admin_required # Only admins can export the full filtered list
def export_employees_csv():
    """Exports the filtered employee list to a CSV file."""
    try:
        # Get filters from query parameters
        search_query = request.args.get('search', '').strip()
        filter_skill_id = request.args.get('skill_id', type=int)
        filter_min_proficiency = request.args.get('min_proficiency', type=int)
        # If proficiency is not explicitly set but skill is, default to 1 for filtering
        if filter_skill_id and filter_min_proficiency is None:
             filter_min_proficiency = 1
        
        # Get the filtered query using the helper
        query = _get_filtered_employees_query(search_query, filter_skill_id, filter_min_proficiency)
        
        # Eager load skills data needed for counts in the export
        # Apply this option specifically for the export context
        query = query.options(joinedload(Employee.skills).joinedload(EmployeeSkill.skill))
        
        # Execute the query to get all matching employees (no pagination)
        employees = query.order_by(Employee.name).all()
        
        # Prepare CSV data
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write Header
        header = [
            'Name', 'Email', 'Clock ID', 'Job Title', 'Level', 'Project', 
            'Start Date', 'Skills Count', 'Training Required Count', 'Training Expired Count'
        ]
        writer.writerow(header)
        
        # Write Data Rows
        today = datetime.utcnow().date()
        for employee in employees:
            # Calculate skill counts (requires employee.skills to be loaded)
            skill_count = len(employee.skills)
            training_required = sum(1 for es in employee.skills if es.skill and es.skill.requires_training)
            expired_count = sum(1 for es in employee.skills if es.training_expiry_date and es.training_expiry_date < today)
            
            row = [
                employee.name,
                employee.email,
                employee.clock_id if employee.clock_id else '',
                employee.job_title,
                employee.level_rel.name if employee.level_rel else '',
                employee.project_rel.name if employee.project_rel else '',
                employee.start_date.strftime('%Y-%m-%d') if employee.start_date else '',
                skill_count,
                training_required,
                expired_count
            ]
            writer.writerow(row)
        
        # Prepare response
        output.seek(0)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'employee_list_{timestamp}.csv'
        
        return Response(
            output,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment;filename={filename}"}
        )
        
    except Exception as e:
        app.logger.error(f"Error exporting employees to CSV: {str(e)}", exc_info=True)
        flash('An error occurred while generating the CSV export.', 'error')
        # Redirect back to index, preserving filters if possible
        return redirect(url_for('index', 
                                search=request.args.get('search', ''),
                                skill_id=request.args.get('skill_id'),
                                min_proficiency=request.args.get('min_proficiency')))

#------------------------------------------------------------------------------
# User Profile Route
#------------------------------------------------------------------------------

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """Allows users to view and edit their profile."""
    user = Employee.query.get_or_404(session['employee_id'])
    # Capture original data
    original_profile_data = {
        'email': user.email,
        'about_me': user.about_me or '',
        'phone_number': user.phone_number or '',
        'linkedin_url': user.linkedin_url or ''
    }
    form = ProfileForm(obj=user) # Pre-populate form
    # Use username and job_title from user object for the form
    form.username.data = user.name
    form.job_title.data = user.job_title
    form.level_name.data = user.level_rel.name if user.level_rel else ''
    form.project_name.data = user.project_rel.name if user.project_rel else ''
    form.start_date_str.data = user.start_date.strftime('%Y-%m-%d') if user.start_date else ''

    if form.validate_on_submit():
        try:
            # Check if email is changing and if it's already taken by another user
            if form.email.data != user.email:
                existing_user = Employee.query.filter(Employee.email == form.email.data, Employee.id != user.id).first()
                if existing_user:
                    flash('That email address is already in use. Please choose a different one.', 'error')
                    return render_template('profile.html', form=form, title="User Profile")

            user.email = form.email.data
            user.about_me = form.about_me.data
            user.phone_number = form.phone_number.data # Save phone number
            user.linkedin_url = form.linkedin_url.data # Save LinkedIn URL
            db.session.commit()
            
            # Log profile changes
            profile_changes = {}
            if user.email != original_profile_data['email']: profile_changes['email'] = {'old': original_profile_data['email'], 'new': user.email}
            if (user.about_me or '') != original_profile_data['about_me']: profile_changes['about_me'] = {'old': original_profile_data['about_me'], 'new': user.about_me or ''}
            if (user.phone_number or '') != original_profile_data['phone_number']: profile_changes['phone_number'] = {'old': original_profile_data['phone_number'], 'new': user.phone_number or ''}
            if (user.linkedin_url or '') != original_profile_data['linkedin_url']: profile_changes['linkedin_url'] = {'old': original_profile_data['linkedin_url'], 'new': user.linkedin_url or ''}
            
            if profile_changes:
                 log_audit(action="Profile Updated", target_type="Employee", target_id=user.id, details=profile_changes)
                 db.session.commit() # Commit log
                 
            flash('Your profile has been updated.', 'success')
            return redirect(url_for('profile'))
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error updating profile for user {user.id}: {str(e)}", exc_info=True)
            flash('An error occurred while updating your profile. Please try again.', 'error')

    elif request.method == 'POST':
        # Form validation failed
        flash('Please correct the errors below.', 'warning')

    return render_template('profile.html', form=form, title="User Profile")

#------------------------------------------------------------------------------
# Application Entry Point
#------------------------------------------------------------------------------

if __name__ == '__main__':
    with app.app_context():
        # Ensure tables are created if they don't exist
        # Consider moving init_db or db.create_all() call here if not handled by Flask-Migrate or similar
        # db.create_all() # Uncomment if you want to ensure tables on every run (might be slow)
        pass # Assuming init_db(app) handles table creation adequately
    app.run(debug=True) 

@app.route('/admin/audit_log')
@admin_required
def admin_audit_log():
    """Displays the audit log entries with pagination."""
    page = request.args.get('page', 1, type=int)
    per_page = 25 # Show more logs per page
    
    log_query = AuditLog.query.order_by(desc(AuditLog.timestamp))
    pagination = log_query.paginate(page=page, per_page=per_page, error_out=False)
    logs = pagination.items
    
    return render_template('audit_log.html', logs=logs, pagination=pagination) 