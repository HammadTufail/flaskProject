from werkzeug.utils import secure_filename
from flask_jwt_extended import create_access_token, get_jwt_identity
from models import Event, Address
from serializers import UserSchema, EventSchema, AddressSchema
import os
import requests
from app import app, db
from models import User, Route
from flask_jwt_extended import jwt_required
import polyline
from shapely.geometry import LineString
from flask import request, jsonify
from math import radians, sin, cos, sqrt, atan2
from serializers import RouteSchema


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

@app.route('/', methods=['GET'])
def hello():
    return jsonify({"hello"}), 201
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
}


@app.route('/create_route', methods=['POST'])
def create_route():
    data = request.get_json()
    start_location = data.get('start_location')
    end_location = data.get('end_location')

    all_routes = {}
    max_co2_emissions = 0  # Keep track of the maximum CO2 emissions

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

                    # Update maximum CO2 emissions if current emission is greater
                    if co2_emissions > max_co2_emissions:
                        max_co2_emissions = co2_emissions

                    encoded_polyline = route.get("overview_polyline", {}).get("points", "")
                    decoded_polyline = polyline.decode(encoded_polyline) if encoded_polyline else []

                    top_routes.append({
                        "start_location": route['legs'][0]['start_location'],
                        "distance": distance,
                        "carbon_emissions": co2_emissions,
                        "encoded_overview_polyline": encoded_polyline,
                        "end_location": route['legs'][0]['end_location'],
                    })

                all_routes[mode] = top_routes

    # Calculating CO2 saved for each route
    for mode, routes in all_routes.items():
        for route in routes:
            route["co2_saved"] = max_co2_emissions - route["carbon_emissions"]  # Calculate CO2 saved

    return jsonify({"message": "Routes fetched", "routes": all_routes, "max":max_co2_emissions}), 200


@app.route('/save_route', methods=['POST'])
@jwt_required()
def save_route():
    user_id = get_jwt_identity()['user_id']
    user = User.query.get_or_404(user_id)

    data = request.get_json()
    mode_of_transportation = data.get('mode_of_transportation')
    estimated_route_points = data.get('estimated_route_points') #encoded polyline string
    carbon_footprint_saved = data.get('carbon_emissions_saved')
    distance = data.get('distance')
    route = Route(
        user=user,
        mode_of_transportation=mode_of_transportation,
        estimated_route_points=estimated_route_points,
        carbon_footprint_saved=carbon_footprint_saved,
        distance=distance,
        start_point=data.get('start_location'),
        end_point=data.get('end_location'),
    )
    db.session.add(route)
    db.session.commit()

    return jsonify({"message": "Route saved", "route_id": route.id}), 200




@app.route('/complete_route/<int:route_id>', methods=['POST'])
@jwt_required()
def complete_route(route_id):
    route = Route.query.get_or_404(route_id)

    data = request.get_json()
    actual_route_points = data.get('actual_route_points')  # Assuming this is an encoded polyline string

    estimated_line = LineString(polyline.decode(route.estimated_route_points))
    actual_line = LineString(polyline.decode(actual_route_points))

    intersection = estimated_line.intersection(actual_line)
    match_percentage = (intersection.length / estimated_line.length) * 100

    if match_percentage >= 70:  # Or your desired threshold
        route.points_awarded = route.carbon_footprint_saved  # Award the user the carbon saved as the points.
        route.actual_route_points = actual_route_points
        user = route.user
        user.points += route.points_awarded  # Update user’s total points
        db.session.commit()

        return jsonify({"message": "Journey completed", "points_awarded": route.points_awarded}), 200
    else:
        return jsonify({"message": "Journey route didn't match the estimated route"}), 400





@app.route('/search_routes', methods=['GET'])
def search_routes():
    start_latitude = float(request.args.get('start_latitude'))
    start_longitude = float(request.args.get('start_longitude'))
    end_latitude = float(request.args.get('end_latitude'))
    end_longitude = float(request.args.get('end_longitude'))
    radius = float(request.args.get('radius', 200))
    print("Testing"+start_longitude,start_longitude,end_latitude,end_longitude,radius)
    if not all([start_latitude, start_longitude, end_latitude, end_longitude]):
        return jsonify({"error": "start_latitude, start_longitude, end_latitude, and end_longitude are required"}), 400

    def haversine(lat1, lon1, lat2, lon2):
        R = 6371.0  # Radius of the Earth in km
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = (sin(dlat / 2) ** 2) + cos(radians(lat1)) * cos(radians(lat2)) * (sin(dlon / 2) ** 2)
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        return R * c  # Distance in km

    # Filter routes manually
    routes = []
    for route in Route.query.all():
        # Assuming start_point and end_point are stored as "lat,lon"
        s_lat, s_lon = map(float, route.start_point.split(','))
        e_lat, e_lon = map(float, route.end_point.split(','))

        if haversine(start_latitude, start_longitude, s_lat, s_lon) <= radius and \
                haversine(end_latitude, end_longitude, e_lat, e_lon) <= radius:
            routes.append(route)

    return jsonify({"routes": RouteSchema(many=True).dump(routes)}), 200


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