from app import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))  # Увеличиваем размер поля
    role = db.Column(db.String(20), nullable=False, default='user')  # 'admin' or 'user'
    projects = db.relationship('Project', backref='owner', lazy='dynamic')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
        
    def is_admin(self):
        return self.role == 'admin'

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    yandex_metrika_counter = db.Column(db.String(20))
    yandex_metrika_token = db.Column(db.String(100))
    yandex_webmaster_host = db.Column(db.String(100))
    keywords = db.relationship('Keyword', backref='project', lazy='dynamic')
    urls = db.relationship('URL', backref='project', lazy='dynamic')

class Keyword(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    keyword = db.Column(db.String(200), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    positions = db.relationship('KeywordPosition', backref='keyword', lazy='dynamic')

class URL(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(500), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    traffic_data = db.relationship('URLTraffic', backref='url', lazy='dynamic')

class KeywordPosition(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    keyword_id = db.Column(db.Integer, db.ForeignKey('keyword.id'), nullable=False)
    position = db.Column(db.Float)
    check_date = db.Column(db.DateTime, default=datetime.utcnow)

class URLTraffic(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url_id = db.Column(db.Integer, db.ForeignKey('url.id'), nullable=False)
    visitors = db.Column(db.Integer)
    check_date = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))
