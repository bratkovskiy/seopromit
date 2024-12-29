import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask
import hvac
from config import Config
from app.extensions import db, login, migrate, socketio, csrf

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Инициализация логирования
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s in %(module)s: %(message)s')
    
    # Настраиваем вывод в консоль
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    
    # Настраиваем root logger
    root_logger = logging.getLogger()
    root_logger.addHandler(console_handler)
    root_logger.setLevel(logging.INFO)
    
    # Настраиваем logger для обновления позиций
    positions_logger = logging.getLogger('update_positions')
    positions_logger.addHandler(console_handler)
    positions_logger.setLevel(logging.INFO)
    
    app.logger.info('Инициализация приложения...')
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login.init_app(app)
    socketio.init_app(app, manage_session=False)
    csrf.init_app(app)
    
    # Initialize Vault client
    vault_client = hvac.Client(
        url=app.config['VAULT_URL'],
        token=app.config['VAULT_TOKEN']
    )
    
    # Явно инициализируем статические файлы
    app.static_folder = 'static'
    app.static_url_path = '/static'
    
    # Register blueprints
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp)
    
    from app.main import bp as main_bp
    app.register_blueprint(main_bp)
    
    app.logger.info('Приложение инициализировано')
    return app

from app import models
