"""
arm.py — CropGuard MeArm + Camera Mount Controller
Fix applied:
  #11  go_home() and go_scan() released the lock BEFORE sleeping.
       Previously time.sleep() was called while holding _lock, blocking
       all other arm calls (pan/tilt etc.) for 300ms.
"""

import time
import threading
import serial_comm

PULSE_MIN = 102
PULSE_MID = 307
PULSE_MAX = 512


def _us_to_pulse(us: int) -> int:
    return int(us * 4096 // 20000)


arm_position = {
    'base':     PULSE_MID,
    'shoulder': _us_to_pulse(1200),
    'elbow':    _us_to_pulse(1800),
    'wrist':    PULSE_MID,
}

cam_position = {
    'pan':  PULSE_MID,
    'tilt': PULSE_MID,
}

arm_busy = False
_lock = threading.Lock()


def _clamp(v: int) -> int:
    return max(PULSE_MIN, min(PULSE_MAX, v))


def _push_arm() -> None:
    serial_comm.arm_position(
        base     = arm_position['base'],
        shoulder = arm_position['shoulder'],
        elbow    = arm_position['elbow'],
        wrist    = arm_position['wrist'],
    )


def _push_cam() -> None:
    serial_comm.cam_pan_tilt(
        pan  = cam_position['pan'],
        tilt = cam_position['tilt'],
    )


def go_home() -> None:
    global arm_busy
    # FIX #11 — update state and send command inside lock, then RELEASE
    # before sleeping so other callers are not blocked during the delay
    with _lock:
        arm_busy = True
        arm_position.update({
            'base':     PULSE_MID,
            'shoulder': _us_to_pulse(1200),
            'elbow':    _us_to_pulse(1800),
            'wrist':    PULSE_MID,
        })
    serial_comm.arm_home()
    time.sleep(0.3)          # sleep outside lock — FIX #11
    with _lock:
        arm_busy = False
    print("[arm] Home position")


def go_scan() -> None:
    global arm_busy
    # FIX #11 — same pattern: lock → update → release → sleep → lock → clear
    with _lock:
        arm_busy = True
        arm_position.update({
            'base':     PULSE_MID,
            'shoulder': _us_to_pulse(1600),
            'elbow':    _us_to_pulse(1400),
            'wrist':    PULSE_MID,
        })
    serial_comm.arm_scan()
    time.sleep(0.3)          # sleep outside lock — FIX #11
    with _lock:
        arm_busy = False
    print("[arm] Scan position")


def pan_left() -> None:
    with _lock:
        arm_position['base'] = _clamp(arm_position['base'] - 40)
        _push_arm()


def pan_right() -> None:
    with _lock:
        arm_position['base'] = _clamp(arm_position['base'] + 40)
        _push_arm()


def tilt_up() -> None:
    with _lock:
        arm_position['wrist'] = _clamp(arm_position['wrist'] + 40)
        _push_arm()


def tilt_down() -> None:
    with _lock:
        arm_position['wrist'] = _clamp(arm_position['wrist'] - 40)
        _push_arm()


def center() -> None:
    go_home()


def cam_pan_left() -> None:
    with _lock:
        cam_position['pan'] = _clamp(cam_position['pan'] - 40)
        _push_cam()


def cam_pan_right() -> None:
    with _lock:
        cam_position['pan'] = _clamp(cam_position['pan'] + 40)
        _push_cam()


def cam_tilt_up() -> None:
    with _lock:
        cam_position['tilt'] = _clamp(cam_position['tilt'] + 40)
        _push_cam()


def cam_tilt_down() -> None:
    with _lock:
        cam_position['tilt'] = _clamp(cam_position['tilt'] - 40)
        _push_cam()


def cam_center() -> None:
    with _lock:
        cam_position.update({'pan': PULSE_MID, 'tilt': PULSE_MID})
    serial_comm.cam_center()


def scan_routine() -> None:
    go_scan()
    time.sleep(1.5)
    go_home()


def is_busy() -> bool:
    with _lock:
        return arm_busy


def cleanup() -> None:
    go_home()


print("[arm] MeArm + camera mount ready (USB serial mode)")
