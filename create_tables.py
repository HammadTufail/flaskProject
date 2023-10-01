from app import app, db  # Import the Flask application instance and the SQLAlchemy db instance

with app.app_context():
    db.create_all()  # Create all tables