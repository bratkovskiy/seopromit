from app import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(120), index=True, unique=True)
    password_hash = db.Column(db.String(256))
    role = db.Column(db.String(20), default='user')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Отношения
    projects = db.relationship('Project', back_populates='user', lazy='dynamic')

    def __repr__(self):
        return f'<User {self.username}>'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return self.role == 'admin'

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    yandex_metrika_counter = db.Column(db.String(50), nullable=False)
    yandex_metrika_token = db.Column(db.String(100), nullable=False)
    yandex_webmaster_host = db.Column(db.String(200), nullable=False)
    yandex_webmaster_token = db.Column(db.String(100), nullable=False)
    yandex_webmaster_user_id = db.Column(db.String(50), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Отношения
    user = db.relationship('User', back_populates='projects')
    keywords = db.relationship('Keyword', backref='project', lazy=True, cascade='all, delete-orphan')
    urls = db.relationship('URL', backref='project', lazy=True, cascade='all, delete-orphan')

class Region(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    yandex_id = db.Column(db.Integer, unique=True, nullable=False)  # ID региона в Яндекс.Вебмастере
    name = db.Column(db.String(100), nullable=False)  # Название региона
    
    # Отношения
    keywords = db.relationship('Keyword', backref='region', lazy=True)

    def __repr__(self):
        return f'<Region {self.name}>'

class Keyword(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    keyword = db.Column(db.String(200), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    region_id = db.Column(db.Integer, db.ForeignKey('region.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_webmaster_update = db.Column(db.DateTime)  # Дата последнего получения данных из Вебмастера
    positions = db.relationship('KeywordPosition', backref='keyword', lazy='dynamic')

class URL(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(500), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_metrika_update = db.Column(db.DateTime)  # Дата последнего получения данных из Метрики
    traffic_data = db.relationship('URLTraffic', backref='url', lazy='dynamic')

class KeywordPosition(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    keyword_id = db.Column(db.Integer, db.ForeignKey('keyword.id'), nullable=False)
    position = db.Column(db.Float)
    check_date = db.Column(db.DateTime, default=datetime.utcnow)  # Когда получили данные
    data_date = db.Column(db.DateTime)  # За какую дату данные из Вебмастера

class URLTraffic(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url_id = db.Column(db.Integer, db.ForeignKey('url.id'), nullable=False)
    visitors = db.Column(db.Integer)
    check_date = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))
