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
    if not os.path.exists(app.config['LOG_DIR']):
        os.makedirs(app.config['LOG_DIR'])
        
    # Настраиваем базовый logger
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s in %(module)s: %(message)s')
    
    # Настраиваем вывод в консоль
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    
    # Настраиваем файловый handler для основного лога
    file_handler = RotatingFileHandler(
        os.path.join(app.config['LOG_DIR'], 'app.log'),
        maxBytes=10485760,
        backupCount=5,
        encoding='cp1251'  # Добавляем кодировку для Windows
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    
    # Настраиваем файловый handler для логов обновления позиций
    positions_handler = RotatingFileHandler(
        os.path.join(app.config['LOG_DIR'], 'update_positions.log'),
        maxBytes=10485760,
        backupCount=5,
        encoding='cp1251'  # Добавляем кодировку для Windows
    )
    positions_handler.setFormatter(formatter)
    positions_handler.setLevel(logging.INFO)
    
    # Настраиваем root logger
    root_logger = logging.getLogger()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    root_logger.setLevel(logging.INFO)
    
    # Настраиваем logger для обновления позиций
    positions_logger = logging.getLogger('app.tasks.update_positions')
    positions_logger.addHandler(positions_handler)
    positions_logger.addHandler(console_handler)
    positions_logger.setLevel(logging.INFO)
    positions_logger.propagate = False
    
    # Настраиваем logger для Яндекс API
    yandex_logger = logging.getLogger('app.yandex')
    yandex_logger.addHandler(positions_handler)
    yandex_logger.addHandler(console_handler)
    yandex_logger.setLevel(logging.INFO)
    yandex_logger.propagate = False
    
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
