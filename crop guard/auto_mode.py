"""
auto_mode.py — CropGuard Autonomous Patrol
All ESP32 communication now goes through serial_comm (USB).
"""

import threading
import time
from datetime import datetime

import serial_comm
import motors
import arm
import sensors
import inference
import brain
import database
from treatments import TREATMENTS

auto_running = False
session_data = {
    'plants_scanned': 0,
    'diseases_found': 0,
    'distance':       0.0,
    'start_time':     None,
    'crops':          [],
    'disease_list':   [],
}

session_lock = threading.Lock()
socketio_ref = None


# ── SocketIO reference ────────────────────────────────────────────

def set_socketio(sio):
    global socketio_ref
    socketio_ref = sio


def emit(event, data):
    if socketio_ref:
        socketio_ref.emit(event, data)


# ── Probe soil ────────────────────────────────────────────────────

def probe_soil(sensor_data_param: dict) -> float:
    emit('robot_action', {'action': 'Probing soil…'})
    motors.stop()

    try:
        # Lower the probe servo
        serial_comm.probe_down()
        time.sleep(2.5)   # settle in soil

        # Read sensors while probe is submerged
        fresh = sensors.get_sensor_data()

        # Retract probe
        serial_comm.probe_up()
        time.sleep(1.0)   # safe to move again
    except Exception as e:
        print(f"[auto_mode] Probe error: {e}")
        fresh = sensors.get_sensor_data()

    soil = fresh.get('soil_percent', sensor_data_param.get('soil_percent', 0))
    lat  = fresh.get('gps_lat', 0)
    lng  = fresh.get('gps_lng', 0)
    zone = f"{round(lat, 4)},{round(lng, 4)}"

    database.log_soil(soil, lat, lng, zone)
    sensors.update_soil(soil)

    emit('soil_reading', {
        'moisture':  soil,
        'timestamp': datetime.now().isoformat(),
    })
    return soil


# ── Scan plant ────────────────────────────────────────────────────

def scan_plant(selected_crops: list, sensor_data: dict):
    emit('robot_action', {'action': 'MeArm raising to scan…'})
    motors.stop()

    arm_thread = threading.Thread(target=arm.scan_routine, daemon=True)
    arm_thread.start()
    time.sleep(0.8)

    emit('robot_action', {'action': 'AI scanning leaf…'})
    disease, confidence = inference.predict_multi_frame(3)
    arm_thread.join(timeout=5)

    with session_lock:
        session_data['plants_scanned'] += 1

    if not disease:
        emit('scan_result', {'disease': 'No disease detected', 'confidence': 0, 'severity': 'none'})
        return None

    severity  = brain.get_severity(disease, confidence)
    treatment = TREATMENTS.get(disease, {})
    is_healthy = treatment.get('severity') == 'none'

    lat  = sensor_data.get('gps_lat', 0)
    lng  = sensor_data.get('gps_lng', 0)
    zone = f"Zone-{round(lat, 3)}"

    if not is_healthy:
        with session_lock:
            session_data['diseases_found'] += 1
            session_data['disease_list'].append(disease)

    emit('robot_action', {'action': f'Detected: {disease} ({confidence}%)'})

    ai_response = brain.ask_claude(
        {
            'disease':       disease,
            'confidence':    confidence,
            'severity':      severity,
            'crop':          disease.split()[0],
            'zone':          zone,
            'soil_moisture': sensor_data.get('soil_percent', 0),
            'temperature':   sensor_data.get('temperature', 0),
            'humidity':      sensor_data.get('humidity', 0),
        },
        sensor_data,
    )

    frame      = inference.get_latest_frame()
    image_path = ''
    if frame is not None:
        ts         = datetime.now().strftime('%Y%m%d_%H%M%S')
        image_path = inference.save_detection_image(frame, disease, ts)

    detection = {
        'disease':       disease,
        'confidence':    confidence,
        'severity':      severity,
        'crop':          disease.split()[0],
        'gps_lat':       lat,
        'gps_lng':       lng,
        'zone':          zone,
        'soil_moisture': sensor_data.get('soil_percent', 0),
        'temperature':   sensor_data.get('temperature', 0),
        'humidity':      sensor_data.get('humidity', 0),
        'ai_analysis':   ai_response,
        'treatment':     treatment,
        'image_path':    image_path,
    }

    database.log_detection(detection)
    database.update_zone_memory(zone, lat, lng, disease if not is_healthy else None)

    emit('disease_detected', {
        **detection,
        'ai_analysis':        ai_response,
        'chemical_treatments': treatment.get('chemical', []),
        'organic_treatments':  treatment.get('organic', []),
        'prevention':          treatment.get('prevention', ''),
        'urgency_hours':       treatment.get('urgency_hours', 48),
        'timestamp':           datetime.now().isoformat(),
    })
    return detection


# ── Auto patrol loop ──────────────────────────────────────────────

def auto_patrol_loop(selected_crops: list):
    global auto_running, session_data

    with session_lock:
        session_data = {
            'plants_scanned': 0,
            'diseases_found': 0,
            'distance':       0.0,
            'start_time':     datetime.now(),
            'crops':          selected_crops,
            'disease_list':   [],
        }

    brain.update_brain_state('patrol_running', True)
    emit('patrol_started', {'crops': selected_crops, 'time': datetime.now().isoformat()})

    stop_counter = 0
    probe_timer  = 0

    while auto_running:
        sensor_data = sensors.get_sensor_data()
        action, msg = brain.decide_next_action(sensor_data)
        brain.update_brain_state('current_action', msg)
        emit('robot_action', {'action': msg})

        if action == 'RETURN_TO_BASE':
            motors.stop()
            emit('alert', {'type': 'battery', 'message': 'Battery critical — returning to base'})
            break

        if action == 'AVOID_OBSTACLE':
            motors.stop()
            time.sleep(0.5)
            motors.backward()
            time.sleep(0.8)
            motors.stop()
            continue

        motors.forward()
        with session_lock:
            session_data['distance'] = round(session_data['distance'] + 0.05, 2)

        stop_counter += 1
        probe_timer  += 1

        # Scan every ~4 s (80 × 50 ms)
        if stop_counter >= 80:
            motors.stop()
            detection    = scan_plant(selected_crops, sensor_data)
            stop_counter = 0
            if detection:
                sev = detection.get('severity', 'low')
                if sev in ('critical', 'high'):
                    probe_soil(sensor_data)

        # Routine soil probe every ~30 s (600 × 50 ms)
        if probe_timer >= 600:
            probe_soil(sensor_data)
            probe_timer = 0

        time.sleep(0.05)

    motors.stop()
    arm.go_home()

    with session_lock:
        duration = int((datetime.now() - session_data['start_time']).seconds / 60)
        session_data['duration'] = duration
        dl = list(set(session_data['disease_list']))
        session_data['disease_list_str'] = ', '.join(dl) if dl else 'None detected'
        summary_input = {**session_data, 'disease_list': session_data['disease_list_str']}

    summary = brain.generate_patrol_summary(summary_input, sensors.get_sensor_data())
    emit('patrol_ended', {**summary_input, 'summary': summary})
    brain.update_brain_state('patrol_running', False)


# ── Public start / stop ───────────────────────────────────────────

def start_patrol(selected_crops: list) -> bool:
    global auto_running
    if auto_running:
        return False
    auto_running = True
    threading.Thread(target=auto_patrol_loop, args=(selected_crops,), daemon=True).start()
    return True


def stop_patrol():
    global auto_running
    auto_running = False
    motors.stop()
    arm.go_home()
    brain.update_brain_state('patrol_running', False)
