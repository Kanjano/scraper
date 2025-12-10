from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=True)
    name = db.Column(db.String(64))
    surname = db.Column(db.String(64))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    newsletter_opt_in = db.Column(db.Boolean, default=False)
    privacy_accepted = db.Column(db.Boolean, default=False)
    
    # OAuth fields
    oauth_provider = db.Column(db.String(20), nullable=True)
    oauth_id = db.Column(db.String(100), nullable=True)
    
    # Relationship with search history
    searches = db.relationship('SearchHistory', backref='user', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class SearchHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    search_term = db.Column(db.String(256), nullable=False)
    filters = db.Column(db.Text)  # JSON string for filters
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<SearchHistory {self.search_term}>'
