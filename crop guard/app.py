"""
app.py — CropGuard Flask + SocketIO Server  (fixed v3)

Fixes in this version:
  - os.environ set BEFORE dotenv/imports so TF sees the flags
  - on_get_history, on_emergency_stop, on_stop_patrol, on_clear_database,
    on_probe_now, on_disconnect all accept **kwargs so flask-socketio can pass
    an optional data argument without TypeError
  - COM7 PermissionError: serial_comm now waits longer between retries and
    skips the port for 30 s after a PermissionError so the log spam stops
"""

import os
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['TF_CPP_MIN_LOG_LEVEL']  = '3'

import threading
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from flask import Flask, render_template, Response, request, jsonify
from flask_socketio import SocketIO, emit

import serial_comm
import sensors
import motors
import arm
import inference
import brain
import auto_mode
import database
from treatments import TREATMENTS, CLASS_NAMES

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'cropguard2024')

socketio = SocketIO(
    app,
    async_mode='threading',
    cors_allowed_origins='*',
    ping_timeout=20,
    ping_interval=10,
    logger=False,
    engineio_logger=False,
)

auto_mode.set_socketio(socketio)


# ── HTTP Routes ────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/video_feed')
def video_feed():
    return Response(
        inference.generate_mjpeg(),
        mimetype='multipart/x-mixed-replace; boundary=frame',
    )


@app.route('/set_crop', methods=['POST'])
def set_crop():
    selected_crop = (
        request.json.get('crop_name', '') if request.is_json
        else request.form.get('crop_name', '')
    )
    inference.set_crop_filter(selected_crop)
    return jsonify({'status': 'success', 'filtered_crop': selected_crop}), 200


@app.route('/set_serial_port', methods=['POST'])
def set_serial_port():
    port = request.json.get('port', '') if request.is_json else ''
    if port:
        serial_comm.set_port(port)
        return jsonify({'status': 'ok', 'port': port}), 200
    return jsonify({'status': 'error', 'message': 'No port specified'}), 400


@app.route('/serial_status')
def serial_status():
    return jsonify({
        'connected': serial_comm.is_connected(),
        'timestamp': datetime.now().isoformat(),
    })


# ── Socket Events ──────────────────────────────────────────────────
# NOTE: flask-socketio may pass a data argument even to handlers that
# declare none — always accept **kwargs to avoid TypeError crashes.

@socketio.on('connect')
def on_connect(**kwargs):
    emit('connected', {'status': 'CropGuard Online', 'time': datetime.now().isoformat()})


@socketio.on('disconnect')
def on_disconnect(**kwargs):
    if not auto_mode.auto_running:
        motors.stop()


@socketio.on('set_crop')
def on_set_crop_socket(data):
    inference.set_crop_filter(data.get('crop_name', ''))


@socketio.on('joystick')
def on_joystick(data):
    if brain.get_brain_state()['mode'] == 'manual':
        motors.move_joystick(float(data.get('x', 0)), float(data.get('y', 0)))
        socketio.emit('motor_state', motors.get_motor_state())


@socketio.on('set_mode')
def on_set_mode(data):
    mode = data.get('mode', 'manual')
    brain.update_brain_state('mode', mode)
    if mode == 'manual':
        auto_mode.stop_patrol()
        motors.stop()
    socketio.emit('mode_changed', {'mode': mode})


@socketio.on('start_patrol')
def on_start_patrol(data):
    crops = data.get('crops', [])
    brain.update_brain_state('selected_crops', crops)
    if crops:
        inference.set_crop_filter(crops[0])
    success = auto_mode.start_patrol(crops)
    socketio.emit('patrol_status', {'running': success, 'crops': crops})


@socketio.on('stop_patrol')
def on_stop_patrol(**kwargs):
    auto_mode.stop_patrol()
    inference.set_crop_filter('')
    socketio.emit('patrol_status', {'running': False})


@socketio.on('emergency_stop')
def on_emergency_stop(**kwargs):
    auto_mode.stop_patrol()
    motors.stop()
    brain.update_brain_state('mode', 'manual')
    socketio.emit('emergency_stopped', {})


@socketio.on('servo_command')
def on_servo_command(data):
    cmd = data.get('command')
    cmds = {
        'pan_left':  arm.pan_left,
        'pan_right': arm.pan_right,
        'tilt_up':   arm.tilt_up,
        'tilt_down': arm.tilt_down,
        'center':    arm.center,
        'home':      arm.go_home,
    }
    if cmd in cmds:
        threading.Thread(target=cmds[cmd], daemon=True).start()
    elif cmd == 'scan':
        threading.Thread(target=arm.scan_routine, daemon=True).start()


@socketio.on('probe_now')
def on_probe_now(**kwargs):
    sensor_data = sensors.get_sensor_data()
    soil = auto_mode.probe_soil(sensor_data)
    socketio.emit('soil_reading', {'moisture': soil, 'timestamp': datetime.now().isoformat()})


@socketio.on('manual_scan')
def on_manual_scan(**kwargs):
    socketio.emit('scan_started', {})
    def do_scan():
        crops     = brain.get_brain_state().get('selected_crops', [])
        detection = auto_mode.scan_plant(crops, sensors.get_sensor_data())
        if not detection:
            socketio.emit('scan_result', {'disease': 'No disease detected', 'confidence': 0})
    threading.Thread(target=do_scan, daemon=True).start()


@socketio.on('ask_claude')
def on_ask_claude(data):
    socketio.emit('claude_thinking', {})
    def get_response():
        response = brain.ask_claude(
            data.get('last_detection', {}),
            sensors.get_sensor_data(),
            question=data.get('question', ''),
        )
        socketio.emit('claude_response', {'response': response, 'timestamp': datetime.now().isoformat()})
    threading.Thread(target=get_response, daemon=True).start()


@socketio.on('get_fertilizer')
def on_get_fertilizer(data):
    socketio.emit('fertilizer_loading', {'id': data.get('id')})
    def fetch_fert():
        plan = brain.get_fertilizer_plan(
            data.get('disease'), data.get('crop'), sensors.get_sensor_data()
        )
        socketio.emit('fertilizer_ready', {'id': data.get('id'), 'plan': plan})
    threading.Thread(target=fetch_fert, daemon=True).start()


@socketio.on('set_speed')
def on_set_speed(data):
    motors.set_speed(int(data.get('speed', 70)))


@socketio.on('get_history')
def on_get_history(**kwargs):
    rows = database.get_recent_detections(20)
    detections = [
        {
            'id': r[0], 'timestamp': r[1], 'disease': r[2], 'confidence': r[3],
            'severity': r[4], 'crop': r[5], 'gps_lat': r[6], 'gps_lng': r[7],
            'zone': r[8], 'soil_moisture': r[9], 'temperature': r[10],
            'humidity': r[11], 'ai_analysis': r[12],
        }
        for r in rows
    ]
    emit('history_data', {'detections': detections})


@socketio.on('clear_database')
def on_clear_database(**kwargs):
    database.clear_database()
    brain.update_brain_state('scan_count', 0)
    socketio.emit('history_data', {'detections': []})


# ── Background threads ─────────────────────────────────────────────

def detection_loop():
    time.sleep(3)
    while True:
        try:
            if not auto_mode.auto_running:
                disease, conf = inference.predict_multi_frame(3)
                if disease and conf > 25:
                    sensor_data = sensors.get_sensor_data()
                    severity    = brain.get_severity(disease, conf)
                    treatment   = TREATMENTS.get(disease, {})
                    is_healthy  = treatment.get('severity') == 'none'
                    crop        = disease.split()[0] if ' ' in disease else disease
                    lat         = sensor_data.get('gps_lat', 0)
                    lng         = sensor_data.get('gps_lng', 0)

                    detection = {
                        'disease':       disease,
                        'confidence':    conf,
                        'severity':      severity,
                        'crop':          crop,
                        'gps_lat':       lat,
                        'gps_lng':       lng,
                        'zone':          f"Zone-{round(lat, 3)}",
                        'soil_moisture': sensor_data.get('soil_percent', 0),
                        'temperature':   sensor_data.get('temperature', 0),
                        'humidity':      sensor_data.get('humidity', 0),
                    }

                    ai_response              = brain.ask_claude(detection, sensor_data)
                    detection['ai_analysis'] = ai_response

                    database.log_detection(detection)
                    brain.update_brain_state(
                        'scan_count',
                        brain.get_brain_state().get('scan_count', 0) + 1,
                    )

                    if is_healthy:
                        socketio.emit('scan_result', {
                            'disease': disease, 'confidence': conf, 'severity': 'none'
                        })
                    else:
                        socketio.emit('disease_detected', {
                            **detection,
                            'ai_analysis':         ai_response,
                            'chemical_treatments': treatment.get('chemical', []),
                            'organic_treatments':  treatment.get('organic', []),
                            'prevention':          treatment.get('prevention', ''),
                            'urgency_hours':       treatment.get('urgency_hours', 48),
                            'timestamp':           datetime.now().isoformat(),
                        })
        except Exception as e:
            print(f"[detection_loop] Error: {e}")
        time.sleep(5)


def sensor_broadcast():
    while True:
        try:
            data = sensors.get_sensor_data()
            socketio.emit('sensor_update', {
                **data,
                'risk_score':  brain.calculate_risk_score(data, []),
                'brain_state': brain.get_brain_state(),
                'motor_state': motors.get_motor_state(),
                'timestamp':   datetime.now().isoformat(),
            })
        except Exception:
            pass
        time.sleep(0.5)


# ── Startup ────────────────────────────────────────────────────────

def startup():
    print("=" * 50)
    print("  CropGuard — USB Serial Mode")
    print("=" * 50)
    database.init_db()
    sensors.start_all_sensors()
    inference.start_camera()
    arm.go_home()
    threading.Thread(target=sensor_broadcast, daemon=True).start()
    threading.Thread(target=detection_loop,   daemon=True).start()
    print("CropGuard ready → http://localhost:5000")
    print("Serial port auto-detected. Override via POST /set_serial_port")


if __name__ == '__main__':
    startup()
    socketio.run(
        app,
        host='0.0.0.0',
        port=5000,
        debug=False,
        use_reloader=False,
        allow_unsafe_werkzeug=True,
    )
