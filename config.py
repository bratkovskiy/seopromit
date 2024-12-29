import os
from dotenv import load_dotenv

load_dotenv()

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Vault settings
    VAULT_URL = os.environ.get('VAULT_URL', 'http://localhost:8200')
    VAULT_TOKEN = os.environ.get('VAULT_TOKEN', 'dev-token')
    
    # App settings
    APP_NAME = os.environ.get('APP_NAME', 'PROMIT SEO')
    
    # Директория для логов
    LOG_DIR = os.path.join(basedir, 'logs')
