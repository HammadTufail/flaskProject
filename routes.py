from flask import request, jsonify
from werkzeug.utils import secure_filename
from flask_jwt_extended import jwt_required, create_access_token, get_jwt_identity
from app import app, db
from models import User, Event, Address
from serializers import UserSchema, EventSchema, AddressSchema
import os
import os
import requests
from flask import jsonify, request
from app import app, db
from models import User, Route
from flask_jwt_extended import jwt_required
import polyline

user_schema = UserSchema()
users_schema = UserSchema(many=True)
event_schema = EventSchema()
events_schema = EventSchema(many=True)
address_schema = AddressSchema()
addresses_schema = AddressSchema(many=True)

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

GOOGLE_MAPS_API_KEY = "AIzaSyDiO4rSQtabv-kWnToMjUbbnKxAKL2b0-I"

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid credentials"}), 401

    access_token = create_access_token(identity={'user_id': user.id})
    return jsonify(access_token=access_token)


@app.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()

    # Validate the required parameters are in the request
    required_parameters = ['username', 'password', 'email', 'phone', 'user_type', 'address_line', 'city', 'state',
                           'country', 'zip_code']
    for param in required_parameters:
        if param not in data:
            return jsonify({"error": f"{param} is required"}), 400

    username = data.get('username')
    password = data.get('password')
    email = data.get('email')
    phone = data.get('phone')
    user_type = data.get('user_type')
    address_line = data.get('address_line')
    city = data.get('city')
    state = data.get('state')
    country = data.get('country')
    zip_code = data.get('zip_code')

    # Validate if user already exists
    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Username already exists"}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already exists"}), 400
    if User.query.filter_by(phone=phone).first():
        return jsonify({"error": "Phone number already exists"}), 400

    # Create a new Address object
    address = Address(
        address_line=address_line,
        city=city,
        state=state,
        country=country,
        zip_code=zip_code
    )

    # Create a new User object
    user = User(
        username=username,
        email=email,
        phone=phone,
        user_type=user_type,
        location=address
    )
    user.set_password(password)  # Set password hash

    # Save the new User and Address to the database
    db.session.add(address)
    db.session.add(user)
    db.session.commit()

    # Create JWT token
    access_token = create_access_token(identity={'user_id': user.id})

    user_schema = UserSchema()
    return jsonify({"message": "User created", "user": user_schema.dump(user), "access_token": access_token}), 201


TRANSPORT_MODES = ['driving', 'transit', 'walking', 'bicycling']  # Add other modes if available in API

EMISSION_FACTORS = {
    "driving": 0.120,  # kg CO2e per passenger-kilometer
    "transit": 0.068,  # kg CO2e per passenger-kilometer
    "bicycling": 0.0,  # kg CO2e per kilometer
    "walking": 0.0,  # kg CO2e per kilometer
    # Add emission factors for other modes
}

import polyline


@app.route('/create_route', methods=['POST'])
def create_route():
    data = request.get_json()
    start_location = data.get('start_location')
    end_location = data.get('end_location')

    all_routes = {}
    for mode in TRANSPORT_MODES:
        response = requests.get(
            'https://maps.googleapis.com/maps/api/directions/json',
            params={
                'origin': start_location,
                'destination': end_location,
                'mode': mode,
                'key': GOOGLE_MAPS_API_KEY
            }
        )

        if response.status_code == 200:
            route_data = response.json()
            if 'routes' in route_data and route_data['routes']:
                top_routes = []
                for route in route_data['routes'][:3]:  # Get top 3 routes
                    distance = route['legs'][0]['distance']['value'] / 1000.0  # Convert to km
                    co2_emissions = distance * EMISSION_FACTORS.get(mode, 0.0)

                    encoded_polyline = route.get("overview_polyline", {}).get("points", "")
                    # Decode the polyline to get the list of coordinates
                    decoded_polyline = polyline.decode(encoded_polyline) if encoded_polyline else []

                    top_routes.append({
                        "distance": distance,
                        "carbon_emissions": co2_emissions,
                        "overview_polyline": decoded_polyline,
                        # Add other relevant info
                    })

                all_routes[mode] = top_routes

    return jsonify({"message": "Routes fetched", "routes": all_routes}), 200


@app.route('/user_info', methods=['GET'])
@jwt_required()
def get_user_info():
    user_id = get_jwt_identity()['user_id']  # Adjust this line if user_id is not in the token
    user = User.query.get(user_id)

    if user is None:
        return jsonify({"error": "User does not exist"}), 400

    user_info = {
        "user_id": user.id,
        "username": user.username,
        "profile_picture": user.profile_picture,
        "email": user.email,
        "phone": user.phone,
        "preferences": user.preferences
    }
    return jsonify(user_info)


@app.route('/users/<int:user_id>/upload_picture', methods=['POST'])
@jwt_required()
def upload_file(user_id):
    user = User.query.get_or_404(user_id)

    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']

    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        user.profile_picture = filepath
        db.session.commit()
        return jsonify({"message": "File uploaded and user profile picture updated"}), 200

    return jsonify({"error": "Invalid file"}), 400


@app.route('/events', methods=['POST'])
@jwt_required()
def create_event():
    data = request.get_json()
    event_type = data.get('event_type')
    creator_id = data.get('creator_id')
    address_line = data.get('address_line')
    city = data.get('city')
    state = data.get('state')
    country = data.get('country')
    zip_code = data.get('zip_code')

    creator = User.query.get(creator_id)
    if creator is None:
        return jsonify({"error": "User does not exist"}), 400

    address = Address(
        address_line=address_line,
        city=city,
        state=state,
        country=country,
        zip_code=zip_code
    )

    event = Event(event_type=event_type, creator=creator, location=address)
    db.session.add(address)
    db.session.add(event)
    db.session.commit()

    return jsonify({"message": "Event created", "event": event_schema.dump(event)}), 201