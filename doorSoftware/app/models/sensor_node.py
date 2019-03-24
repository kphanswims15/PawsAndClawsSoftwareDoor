from models.shared import db



class SensorNode(db.Model):
    __tablename__ = "sensor_node"
    id = db.Column(db.Integer, primary_key=True)
    mac = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String, nullable=True)
    location = db.Column(db.String, nullable=True)
    sensors = db.relationship("Sensor", backref="sensor_node", lazy='joined')
    