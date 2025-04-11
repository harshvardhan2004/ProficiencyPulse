# Flask Skills Matrix Application
# This application manages employee skills, training, and professional development
# Author: [Your Name]
# Version: 1.0

# Standard library imports
from datetime import datetime, timedelta

# Third-party imports
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_file, after_this_request
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
    Supports filtering by skill and minimum proficiency.
    Uses pagination for the employee list if viewed by an admin.
    """
    # Get search, filter, and page parameters
    search_query = request.args.get('search', '').strip()
    filter_skill_id = request.args.get('skill_id', type=int)
    # Default proficiency to 1 if a skill is selected, otherwise None
    default_proficiency = 1 if filter_skill_id else None 
    filter_min_proficiency = request.args.get('min_proficiency', default=default_proficiency, type=int)
    page = request.args.get('page', 1, type=int)
    per_page = 10 # Or get from config
    
    # Fetch all skills for the filter dropdown
    all_skills = Skill.query.order_by(Skill.name).all()
    today = datetime.utcnow().date()

    # Base query depending on user type
    if session.get('is_admin', False):
        query = Employee.query
    else:
        # Non-admins see only themselves, no pagination needed for a single record
        employee = Employee.query.options(
            joinedload(Employee.skills).joinedload(EmployeeSkill.skill),
            joinedload(Employee.level_rel),
            joinedload(Employee.project_rel)
        ).filter_by(id=session.get('employee_id')).first_or_404()
        
        # Render a slightly different context or potentially a different template?
        # For now, returning a list containing the single employee for template consistency.
        return render_template('index.html', 
                             employees=[employee], # Pass as a list
                             skills=all_skills, 
                             today=today,
                             current_employee_id=session.get('employee_id'),
                             is_admin=False,
                             search_query=search_query,
                             filter_skill_id=None, # No filters for single user view
                             filter_min_proficiency=None,
                             pagination=None) # No pagination for single user view
    
    # --- Admin View Logic --- 
    
    # Apply search if query exists (only for admin view)
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

    # Apply skill filter if provided (only for admin view)
    if filter_skill_id:
        query = query.join(EmployeeSkill).filter(
            EmployeeSkill.skill_id == filter_skill_id
        )
        if filter_min_proficiency:
            # Ensure proficiency is within a valid range (e.g., 1-5)
            valid_proficiency = max(1, min(filter_min_proficiency, 5))
            query = query.filter(EmployeeSkill.proficiency_level >= valid_proficiency)

    # Eager load relationships needed in the template loop
    # Apply options *after* filtering joins are established
    query = query.options(
        joinedload(Employee.skills).joinedload(EmployeeSkill.skill),
        joinedload(Employee.level_rel),
        joinedload(Employee.project_rel)
    )

    # Order and paginate (only for admin view)
    pagination = query.order_by(Employee.name).paginate(
        page=page, 
        per_page=per_page, 
        error_out=False
    )
    employees_paginated = pagination.items
    
    return render_template('index.html', 
                         employees=employees_paginated, # Pass the items for the current page
                         skills=all_skills, # Pass all skills for header AND filter
                         today=today,
                         current_employee_id=session.get('employee_id'),
                         is_admin=True,
                         search_query=search_query,
                         filter_skill_id=filter_skill_id,
                         filter_min_proficiency=filter_min_proficiency,
                         pagination=pagination) # Pass the pagination object

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

    # Eager load skills and the related skill object for efficiency
    employee = Employee.query.options(
        joinedload(Employee.skills).joinedload(EmployeeSkill.skill)
    ).get_or_404(employee_id)
    all_skills = Skill.query.order_by(Skill.name).all() # Fetch all possible skills for the form

    if request.method == 'POST':
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
                        # Update existing skill only if data has changed
                        employee_skill = existing_employee_skills[skill_id]
                        needs_update = False
                        if employee_skill.proficiency_level != level:
                            employee_skill.proficiency_level = level
                            needs_update = True
                        if employee_skill.last_training_date != last_training_date:
                             employee_skill.last_training_date = last_training_date
                             needs_update = True
                        # Treat empty string notes as None for comparison
                        current_notes = employee_skill.notes if employee_skill.notes else ''
                        submitted_notes = notes if notes else ''
                        if current_notes != submitted_notes:
                             employee_skill.notes = notes if notes else None
                             needs_update = True

                        if needs_update:
                            employee_skill.calculate_and_set_expiry_date() # Recalculate expiry
                            db.session.add(employee_skill) # Add to session if updated (SQLAlchemy handles updates)

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

            # Delete skills that were previously assigned but not in the form submission
            skill_ids_to_delete = set(existing_employee_skills.keys()) - submitted_skill_ids
            for skill_id in skill_ids_to_delete:
                skill_to_delete = existing_employee_skills[skill_id]
                db.session.delete(skill_to_delete)

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
    
    # Pass the necessary data directly to the main template
    return render_template('admin.html',
                         projects=projects,
                         levels=levels,
                         skills=skills_paginated,  # Pass the paginated object
                         employees=employees_paginated, # Pass the paginated object
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

@app.route('/admin/database/backup')
@admin_required
def backup_database():
    """Create a backup of the database in SQLite format."""
    try:
        # Create a temporary SQLite database
        backup_db_path = 'backup_skills_matrix.db'
        backup_uri = f'sqlite:///{backup_db_path}'
        
        # Create engine for backup database
        backup_engine = db.create_engine(backup_uri)
        
        # Create all tables in the backup database
        db.Model.metadata.create_all(backup_engine)
        
        # Create a new session for the backup database
        from sqlalchemy.orm import sessionmaker
        BackupSession = sessionmaker(bind=backup_engine)
        backup_session = BackupSession()
        
        # Get all models from the current database
        models = [Level, Project, Employee, Skill, EmployeeSkill]
        
        # Copy data from each model
        for model in models:
            # Get all records from the current database
            records = model.query.all()
            
            # Insert records into backup database
            for record in records:
                # Create a new instance without SQLAlchemy's instrumentation
                backup_record = model()
                for column in model.__table__.columns:
                    setattr(backup_record, column.name, getattr(record, column.name))
                backup_session.add(backup_record)
        
        # Commit the backup
        backup_session.commit()
        backup_session.close()
        
        # Send the file
        from flask import send_file
        import os
        from datetime import datetime
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        download_name = f'skills_matrix_backup_{timestamp}.db'
        
        return_data = send_file(
            backup_db_path,
            mimetype='application/x-sqlite3',
            as_attachment=True,
            download_name=download_name
        )
        
        # Clean up the temporary file after sending
        @after_this_request
        def remove_file(response):
            try:
                os.remove(backup_db_path)
            except Exception as e:
                app.logger.error(f"Error removing temporary backup file: {e}")
            return response
            
        return return_data
        
    except Exception as e:
        flash(f'Error creating backup: {str(e)}', 'error')
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
# Application Entry Point
#------------------------------------------------------------------------------

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True) 