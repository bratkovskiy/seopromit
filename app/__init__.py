from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from config import Config
import hvac

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    
    # Set up login configuration
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'
    
    # Initialize Vault client
    vault_client = hvac.Client(
        url=app.config['VAULT_URL'],
        token=app.config['VAULT_TOKEN']
    )
    
    # Register blueprints
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp)
    
    from app.main import bp as main_bp
    app.register_blueprint(main_bp)
    
    return app

from app import models
