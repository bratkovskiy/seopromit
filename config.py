import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'mysql://root:password@localhost/seopromit'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Vault settings
    VAULT_URL = os.environ.get('VAULT_URL', 'http://localhost:8200')
    VAULT_TOKEN = os.environ.get('VAULT_TOKEN')
    
    # App settings
    APP_NAME = os.environ.get('APP_NAME', 'PROMIT SEO')