"""
sensors.py — CropGuard Sensor Interface
Reads live data from serial_comm (ESP32-S3 via USB).
Drop-in replacement for the old WiFi HTTP version.
"""

import serial_comm


def get_sensor_data() -> dict:
    """Return a full sensor snapshot. Always succeeds (returns last known if offline)."""
    return serial_comm.get_sensor_data()


def update_soil(value: float):
    """Cache a fresh soil reading received after a manual probe."""
    serial_comm.update_soil(value)


def start_all_sensors():
    """
    No-op — serial_comm auto-starts its background thread at import.
    Called by app.py startup(); kept for API compatibility.
    """
    print(f"[sensors] USB serial backend active. ESP32 online: {serial_comm.is_connected()}")
