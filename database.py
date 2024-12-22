from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect

# Initialize SQLAlchemy instance
db = SQLAlchemy()

def init_db(app):
    """Initialize the database with the app"""
    db.init_app(app)
    
    # Create tables only if they don't exist
    with app.app_context():
        # Get database engine
        engine = db.get_engine()
        inspector = inspect(engine)
        
        # Get existing tables
        existing_tables = inspector.get_table_names()
        
        # Create only tables that don't exist
        db.Model.metadata.create_all(bind=engine,
                                   tables=[table for table in db.Model.metadata.tables.values()
                                         if table.name not in existing_tables]) 