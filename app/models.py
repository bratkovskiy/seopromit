from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db, login

@login.user_loader
def load_user(id):
    return User.query.get(int(id))

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(120), index=True, unique=True)
    password_hash = db.Column(db.String(256))  # Увеличиваем длину до 256
    role = db.Column(db.String(20), default='user')  # Добавляем поле role
    projects = db.relationship('Project', backref='user', lazy='dynamic')
    
    def __repr__(self):
        return '<User {}>'.format(self.username)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
        
    def is_admin(self):
        return self.role == 'admin'

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64))
    url = db.Column(db.String(256))
    yandex_metrika_counter = db.Column(db.String(256))
    yandex_metrika_token = db.Column(db.String(256))
    yandex_webmaster_host = db.Column(db.String(256))
    yandex_webmaster_token = db.Column(db.String(256))
    yandex_webmaster_user_id = db.Column(db.String(256))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    keywords = db.relationship('Keyword', backref='project', lazy='dynamic', cascade='all, delete-orphan')
    urls = db.relationship('URL', backref='project', lazy='dynamic', cascade='all, delete-orphan')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return '<Project {}>'.format(self.name)

class Region(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.Integer, unique=True)
    keywords = db.relationship('Keyword', backref='region', lazy='dynamic')
    
    def __repr__(self):
        return '<Region {}>'.format(self.name)

class Keyword(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    keyword = db.Column(db.String(256))
    project_id = db.Column(db.Integer, db.ForeignKey('project.id', ondelete='CASCADE'))
    region_id = db.Column(db.Integer, db.ForeignKey('region.id'))
    url_id = db.Column(db.Integer, db.ForeignKey('url.id', ondelete='CASCADE'))  # Добавляем связь с URL
    positions = db.relationship('KeywordPosition', backref='keyword', lazy='dynamic', cascade='all, delete-orphan')
    url = db.relationship('URL', backref=db.backref('keyword_list', lazy='dynamic'))  # Исправляем backref
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_webmaster_update = db.Column(db.DateTime)
    
    def __repr__(self):
        return '<Keyword {}>'.format(self.keyword)

class KeywordPosition(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    keyword_id = db.Column(db.Integer, db.ForeignKey('keyword.id'))
    position = db.Column(db.Integer)
    check_date = db.Column(db.DateTime, default=datetime.utcnow)
    data_date_start = db.Column(db.DateTime)
    data_date_end = db.Column(db.DateTime)
    
    def __repr__(self):
        return '<Position {} for Keyword {}>'.format(self.position, self.keyword_id)

class URL(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(500), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id', ondelete='CASCADE'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_metrika_update = db.Column(db.DateTime)
    traffic_data = db.relationship('URLTraffic', backref='url', lazy='dynamic', cascade='all, delete-orphan')
    
class URLTraffic(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url_id = db.Column(db.Integer, db.ForeignKey('url.id', ondelete='CASCADE'))
    visits = db.Column(db.Integer)
    check_date = db.Column(db.DateTime, default=datetime.utcnow)
