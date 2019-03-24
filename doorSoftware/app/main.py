
from flask import Flask
from flask import request
from flask import make_response
from flask import jsonify
import flask_sqlalchemy as sqlalchemy
from flask_cors import CORS
import uuid
import calendar
import time
from models.shared import db
from models.sensor import Sensor, SensorType
from models.sensor_reading import SensorReading
from models.sensor_node import SensorNode

from models.systemstats import systemstats


sensors = "/sensors/"
web = "/web/"



def create_app():
    app = Flask(__name__)
    CORS(app)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///security_system.db'
    db.init_app(app)
    print("created app!")
    
    return app

app = create_app()
app.app_context().push()
db.create_all() # the order of this and the previous 2 lines is important

def timestamp():
    return calendar.timegm(time.gmtime()) * 1000

def validatePasscode(request):
    passcode = request.form.get("passcode", None)
    if(passcode != systemstats.passcode):
        return False
    else:
        return True

def mapStatusToState(status):
    if(status == "armed"):
        return 201
    elif(status == "disarmed"):
        return 202
    elif(status == "tripped"):
        return 203
    
def evaluteThreshold(val, gt_eq, threshold):
    if(gt_eq):
        print("was greater than")
        return float(val) >= float(threshold)
    else:
        return float(val) < float(threshold)

def doEvaluations():
    alarm_tripped = False
    sensors = Sensor.query.all()
    for sensor in sensors:
        sensor_id = sensor.id
        reading = SensorReading.query.filter_by(sensor_id=sensor_id).order_by(SensorReading.time.desc()).first()
        if(evaluteThreshold(reading.val, sensor.greater_than_or_eq, sensor.threshold)):
            print("alarm trip")
            alarm_tripped = True

    return alarm_tripped

def evaluteThresholds():
    # this does nothing rn
    alarm_tripped = doEvaluations()

    if(alarm_tripped and systemstats.system_status == "armed"):
        systemstats.system_status = "tripped"
    

@app.route(sensors + "register", methods=["POST"])
def register():
    mac_address = str(request.data).split("=")[1][:-1]
    
    if(mac_address == None):
        return str(0), 500 # return error
    
    # Now that we can be sure we got what we needed
    
    # Check to see if MAC address is already in database
    query = SensorNode.query.filter_by(mac=str(mac_address)).limit(1)

    if(query.count() == 1):
        # sensor node has already been registered 
        # (or we have a mac address collision!)
        print(str(query))
    else:
        newNode = SensorNode(
            mac=mac_address
        )
        db.session.add(newNode)
        db.session.commit()
    
    return "", 200

@app.route(sensors + "report", methods=["POST"])
def report():
    [mac_address, val] = str(request.data).split("&")
    mac_address = mac_address.split("=")[1]
    print(val)
    sensor_val = float(val.split("=")[1][:-1])
    print(sensor_val)
    if(mac_address == None):
        return str(0), 500 # return error
    
    if(sensor_val == None):
        return str(0), 500
    else:
        sensor_node = SensorNode.query.filter_by(mac=str(mac_address)).first()
        if(sensor_node == None):
            return str(0), 204
        if(len(sensor_node.sensors) == 0):
            return str(0), 204
        sensor_id = sensor_node.sensors[0].id
        newSensorReading = SensorReading(
            time=timestamp(),
            val=sensor_val,
            sensor_id=sensor_id
        )
        db.session.add(newSensorReading)
        db.session.commit()
        print("commited new sensor reading")
        evaluteThresholds()
        return "", mapStatusToState(systemstats.system_status)
        
        
@app.route(web + "check_passcode", methods=["POST"])
def check_passcode():
    response = {}
    submitted_passcode = request.form.get("passcode", None)
    if(submitted_passcode == None):
        errors = []
        result = "bad"
        response["result"] = result
        errors.append("no passcode submitted")
        response["errors"] = errors
        return jsonify(response), 500
    
    if(submitted_passcode != systemstats.passcode):
        result = "bad_pass"
    else:
        result = "good_pass"
    response["result"] = result
    return jsonify(response)

@app.route(web + "get_system_state", methods=["POST"])
def get_system_state():
    response = {}
    if(not validatePasscode(request)):
        response["errors"] = ["bad_pass"]
        return jsonify(response), 200
    response["result"] = systemstats.system_status
    return jsonify(response), 200

@app.route(web + "get_sensors", methods=["POST"])
def get_sensors():
    response = {}
    if(not validatePasscode(request)):
        response["errors"] = ["bad_pass"]
        return jsonify(response), 200
    
    sensorlist = []
    for sensor in db.session.query(SensorNode).all():
        tempdict = {}
        readingslist = []
        num_sensors = len(sensor.sensors)
        if(num_sensors > 0):
            readings = sensor.sensors[0].readings.order_by(SensorReading.time.desc()).first()
            if(readings != None):
                theReading = readings.__dict__ # lists aren't mutable lol
                theReading.pop("_sa_instance_state")
                readingslist = theReading
            sensorsdict = sensor.sensors[0].__dict__
            
            sensorsdict.pop("_sa_instance_state")
            try:
                sensorsdict.pop("readings")
            except:
                pass
        sensor.__dict__.pop("_sa_instance_state")
        sensor.__dict__.pop("sensors")
        tempdict = sensor.__dict__
        if(num_sensors > 0):
            tempdict["sensors"] = sensorsdict
            tempdict["sensors"]["reading"] = readingslist
        sensorlist.append(tempdict)
    response["sensors"] = sensorlist
    return jsonify(response), 200

@app.route(web + "update_sensor", methods=["POST"])
def update_sensor():
    response = {}
    if(not validatePasscode(request)):
        response["errors"] = ["bad_pass"]
        return jsonify(response), 200
    query = SensorNode.query.filter_by(id=request.form.get("id")).first()
    if(query == None):
        response["errors"] = ["invalid_id"]
    else:
        query.name = request.form.get("name")
        query.location = request.form.get("location")
        if(query.sensors == []):
            newSensor = Sensor(
                type=request.form.get("type"),
                threshold=request.form.get("threshold")
            )
            db.session.add(newSensor)
            db.session.add(query)
            query.sensors.append(newSensor)
            db.session.commit()
        else:
            query.sensors[0].type = request.form.get("type")
            query.sensors[0].threshold = request.form.get("threshold")
            db.session.commit()
        query = SensorNode.query.filter_by(id=request.form.get("id")).first()
        sensor = db.session.query(SensorNode).filter_by(id=request.form.get("id")).first()
        sensor.__dict__.pop("_sa_instance_state")
        
        sensorsdict = sensor.sensors[0].__dict__
        sensorsdict.pop("_sa_instance_state")
        
        sensor.__dict__.pop("sensors")
        
        print(str(sensor.__dict__))
        
        #sensor.sensor.__dict__.pop("_sa_instance_state")
        response["sensor"] = sensor.__dict__
        response["sensor"]["sensors"] = sensorsdict
        #response["sensor"] = sensor.sensors[0].__dict__
        
    return jsonify(response)
        
    
    
@app.route(web + "set_state", methods=["POST"])
def set_state():
    response = {}
    if(not validatePasscode(request)):
        response["errors"] = ["bad_pass"]
        return jsonify(response), 200

    requested_state = request.form.get("state")
    if(requested_state in ["armed", "disarmed"]):
        if(requested_state == "armed" and doEvaluations() == True):
            systemstats.system_status = "disarmed"
        else:
            systemstats.system_status = requested_state
    response["state"] = systemstats.system_status
    return jsonify(response)

@app.route(web + "get_state", methods=["POST"])
def get_state():
    response = {}
    if(not validatePasscode(request)):
        response["errors"] = ["bad_pass"]
        return jsonify(response), 200
    response["state"] = systemstats.system_status
    return jsonify(response)
#@app.route(web + "register", methods=["POST"])

