"""
motors.py — CropGuard Motor Controller
Fix applied:
  #12  stop() always sends the serial command — was silently dropped when
       direction was already 'stop' (e.g. after startup or reconnect)
"""

import serial_comm

motor_state = {
    'left_speed':  0,
    'right_speed': 0,
    'direction':   'stop',
    'steering':    0,
}

_current_speed_pct = 70   # 0-100


def set_speed(speed_pct: int) -> None:
    global _current_speed_pct
    _current_speed_pct = max(0, min(100, speed_pct))
    serial_comm.set_speed(_current_speed_pct)


def _pwm() -> int:
    return int(_current_speed_pct * 255 / 100)


def forward(speed=None) -> None:
    if motor_state['direction'] != 'forward':
        motor_state.update({'direction': 'forward',
                            'left_speed': _current_speed_pct,
                            'right_speed': _current_speed_pct})
        serial_comm.motor('forward', _pwm())


def backward(speed=None) -> None:
    if motor_state['direction'] != 'backward':
        motor_state.update({'direction': 'backward',
                            'left_speed': _current_speed_pct,
                            'right_speed': _current_speed_pct})
        serial_comm.motor('backward', _pwm())


def stop() -> None:
    # FIX #12 — always send stop command unconditionally.
    # Previous version skipped send when direction was already 'stop',
    # which meant the ESP32 never received stop after a reconnect or crash.
    motor_state.update({'direction': 'stop', 'left_speed': 0,
                        'right_speed': 0, 'steering': 0})
    serial_comm.motor_stop()


def steer(value: float) -> None:
    motor_state['steering'] = round(value * 100)


def move_joystick(x: float, y: float) -> None:
    steer(x * 0.8)
    if y > 0.3:
        forward()
    elif y < -0.3:
        backward()
    elif x > 0.3:
        if motor_state['direction'] != 'right':
            motor_state['direction'] = 'right'
            serial_comm.motor('right', _pwm())
    elif x < -0.3:
        if motor_state['direction'] != 'left':
            motor_state['direction'] = 'left'
            serial_comm.motor('left', _pwm())
    else:
        stop()


def get_motor_state() -> dict:
    return motor_state.copy()


def cleanup() -> None:
    stop()


print("[motors] L298N driver ready (USB serial mode)")
