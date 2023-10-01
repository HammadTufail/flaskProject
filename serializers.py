from flask_marshmallow import Marshmallow
from models import User, Event, Address, Route

ma = Marshmallow()


class UserSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = User
        load_instance = True


class EventSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Event
        load_instance = True


class AddressSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Address
        load_instance = True

class RouteSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Route
        load_instance = True