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


# ---------------------------------------------------------------------------
# AdaptiveSearchOptimizer — learning data
# ---------------------------------------------------------------------------

class ClickLog(db.Model):
    """Tracks user clicks on search results to learn query→product correlations."""
    __tablename__ = 'click_log'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    query = db.Column(db.String(256), nullable=False, index=True)
    normalized_query = db.Column(db.String(256), nullable=False, index=True)
    product_key = db.Column(db.String(512), nullable=False, index=True)
    product_name = db.Column(db.String(512), nullable=True)
    site = db.Column(db.String(64), nullable=True)
    click_rank = db.Column(db.Integer, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)


class QueryFailure(db.Model):
    """Logs queries that returned zero results — feeds crawl gap analysis."""
    __tablename__ = 'query_failure'
    id = db.Column(db.Integer, primary_key=True)
    query = db.Column(db.String(256), nullable=False, index=True)
    normalized_query = db.Column(db.String(256), nullable=False, index=True)
    results_count = db.Column(db.Integer, default=0)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)


class QueryImpression(db.Model):
    """Counts how often a query is run — denominator for CTR / popularity."""
    __tablename__ = 'query_impression'
    id = db.Column(db.Integer, primary_key=True)
    normalized_query = db.Column(db.String(256), nullable=False, index=True)
    results_count = db.Column(db.Integer, default=0)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)


class ProductVariant(db.Model):
    """Alternative spellings / aliases / abbreviations for a canonical product name."""
    __tablename__ = 'product_variant'
    id = db.Column(db.Integer, primary_key=True)
    product_key = db.Column(db.String(512), nullable=False, index=True)
    main_name = db.Column(db.String(512), nullable=False)
    variant = db.Column(db.String(256), nullable=False, index=True)
    source = db.Column(db.String(32), default='rules')  # rules|click|manual
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('product_key', 'variant', name='uq_product_variant'),)


class QueryCorrelation(db.Model):
    """Aggregated query→product correlation strength (Bayesian-updated by clicks)."""
    __tablename__ = 'query_correlation'
    id = db.Column(db.Integer, primary_key=True)
    normalized_query = db.Column(db.String(256), nullable=False, index=True)
    product_key = db.Column(db.String(512), nullable=False, index=True)
    product_name = db.Column(db.String(512), nullable=True)
    click_count = db.Column(db.Integer, default=0)
    impression_count = db.Column(db.Integer, default=0)
    score = db.Column(db.Float, default=0.0)  # smoothed CTR-style score
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (
        db.UniqueConstraint('normalized_query', 'product_key', name='uq_query_product'),
    )
