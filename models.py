from datetime import datetime
from app import db
from werkzeug.security import generate_password_hash, check_password_hash


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    profile_picture = db.Column(db.String(255), nullable=True)
    preferences = db.Column(db.String(255), nullable=True)
    user_type = db.Column(db.String(50), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey('address.id'), nullable=False)
    location = db.relationship('Address', back_populates='user')
    events = db.relationship('Event', back_populates='creator', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    creator = db.relationship('User', back_populates='events')
    location_id = db.Column(db.Integer, db.ForeignKey('address.id'), nullable=False)
    location = db.relationship('Address', back_populates='event')


class Address(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    address_line = db.Column(db.String(255), nullable=False)
    city = db.Column(db.String(50), nullable=False)
    state = db.Column(db.String(50), nullable=False)
    country = db.Column(db.String(50), nullable=False)
    zip_code = db.Column(db.String(20), nullable=False)
    user = db.relationship('User', uselist=False, back_populates='location')
    event = db.relationship('Event', uselist=False, back_populates='location')

class Route(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', back_populates='routes')
    mode_of_transportation = db.Column(db.String(50), nullable=False)
    distance = db.Column(db.Float, nullable=False)
    carbon_footprint_saved = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    actual_route_points = db.Column(db.Text, nullable=True)  # Stores encoded polyline after journey completion
    points_awarded = db.Column(db.Integer, default=0)  # Points to award the user after journey completion
    estimated_route_points = db.Column(db.Text, nullable=True)  # To store the encoded polyline string
    start_point = db.Column(db.String(255), nullable=True)
    end_point = db.Column(db.String(255), nullable=True)

User.routes = db.relationship('Route', back_populates='user', lazy='dynamic')
