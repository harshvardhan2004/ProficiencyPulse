import os
from dotenv import load_dotenv
from os import environ
from datetime import timedelta

# Load environment variables from .env file
load_dotenv()

class Config:
    SECRET_KEY = environ.get('SECRET_KEY', 'dev-key')
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:123456@localhost/skillsmatrix'

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Session settings
    PERMANENT_SESSION_LIFETIME = timedelta(days=31)  # Session will last for 31 days
    SESSION_COOKIE_SECURE = environ.get('FLASK_ENV') == 'production'  # Secure in production
    SESSION_COOKIE_HTTPONLY = True  # Prevent JavaScript access to session cookie
    SESSION_COOKIE_SAMESITE = 'Lax'  # CSRF protection

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///skills_matrix.db'

class ProductionConfig(Config):
    DEBUG = False
    DB_USER = os.getenv('DB_USER', 'root')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '123456')
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_NAME = os.getenv('DB_NAME', 'skills_matrix')
    SQLALCHEMY_DATABASE_URI = f'mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}'

# Select configuration based on environment
config = ProductionConfig if os.getenv('FLASK_ENV') == 'production' else DevelopmentConfig 