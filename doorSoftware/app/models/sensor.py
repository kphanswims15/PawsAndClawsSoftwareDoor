from models.shared import db
import enum
class SensorType(enum.Enum):
    binary = 0
    range = 1


class Sensor(db.Model):
    __tablename__ = "sensor"
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.Integer)
    threshold = db.Column(db.Float, nullable=False)
    greater_than_or_eq = db.Column(db.Boolean, nullable=False, default=True)
    sensor_node_id = db.Column(db.Integer, db.ForeignKey("sensor_node.id"))
    readings = db.relationship("SensorReading", backref="sensor", lazy='dynamic')