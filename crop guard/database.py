"""
database.py — CropGuard SQLite Database Layer
Handles all persistent storage: detections, soil logs, zone memory.
"""

import os
import sqlite3
import threading
from datetime import datetime

DB_PATH = os.getenv('DB_PATH', 'data/cropguard.db')
_lock = threading.Lock()


def _get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create all tables if they don't exist."""
    with _lock:
        conn = _get_conn()
        cur = conn.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS detections (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp     TEXT    NOT NULL,
                disease       TEXT    NOT NULL,
                confidence    REAL    DEFAULT 0,
                severity      TEXT    DEFAULT 'low',
                crop          TEXT    DEFAULT '',
                gps_lat       REAL    DEFAULT 0,
                gps_lng       REAL    DEFAULT 0,
                zone          TEXT    DEFAULT '',
                soil_moisture REAL    DEFAULT 0,
                temperature   REAL    DEFAULT 0,
                humidity      REAL    DEFAULT 0,
                ai_analysis   TEXT    DEFAULT '',
                image_path    TEXT    DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS soil_logs (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT    NOT NULL,
                moisture  REAL    DEFAULT 0,
                gps_lat   REAL    DEFAULT 0,
                gps_lng   REAL    DEFAULT 0,
                zone      TEXT    DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS zone_memory (
                zone        TEXT PRIMARY KEY,
                gps_lat     REAL    DEFAULT 0,
                gps_lng     REAL    DEFAULT 0,
                last_disease TEXT   DEFAULT '',
                visit_count INTEGER DEFAULT 0,
                last_visit  TEXT    DEFAULT ''
            );
        """)
        conn.commit()
        conn.close()
    print(f"[database] SQLite ready → {DB_PATH}")


def log_detection(detection: dict) -> None:
    """Insert one detection record."""
    with _lock:
        conn = _get_conn()
        try:
            conn.execute("""
                INSERT INTO detections
                    (timestamp, disease, confidence, severity, crop,
                     gps_lat, gps_lng, zone, soil_moisture,
                     temperature, humidity, ai_analysis, image_path)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                datetime.now().isoformat(),
                detection.get('disease', ''),
                detection.get('confidence', 0),
                detection.get('severity', 'low'),
                detection.get('crop', ''),
                detection.get('gps_lat', 0),
                detection.get('gps_lng', 0),
                detection.get('zone', ''),
                detection.get('soil_moisture', 0),
                detection.get('temperature', 0),
                detection.get('humidity', 0),
                detection.get('ai_analysis', ''),
                detection.get('image_path', ''),
            ))
            conn.commit()
        finally:
            conn.close()


def log_soil(moisture: float, lat: float, lng: float, zone: str) -> None:
    """Insert one soil moisture reading."""
    with _lock:
        conn = _get_conn()
        try:
            conn.execute("""
                INSERT INTO soil_logs (timestamp, moisture, gps_lat, gps_lng, zone)
                VALUES (?,?,?,?,?)
            """, (datetime.now().isoformat(), round(moisture, 1), lat, lng, zone))
            conn.commit()
        finally:
            conn.close()


def update_zone_memory(zone: str, lat: float, lng: float, disease) -> None:
    """Upsert zone visit record."""
    with _lock:
        conn = _get_conn()
        try:
            conn.execute("""
                INSERT INTO zone_memory (zone, gps_lat, gps_lng, last_disease, visit_count, last_visit)
                VALUES (?, ?, ?, ?, 1, ?)
                ON CONFLICT(zone) DO UPDATE SET
                    gps_lat      = excluded.gps_lat,
                    gps_lng      = excluded.gps_lng,
                    last_disease = CASE WHEN excluded.last_disease != ''
                                        THEN excluded.last_disease
                                        ELSE last_disease END,
                    visit_count  = visit_count + 1,
                    last_visit   = excluded.last_visit
            """, (zone, lat, lng, disease or '', datetime.now().isoformat()))
            conn.commit()
        finally:
            conn.close()


def get_recent_detections(limit: int = 20) -> list:
    """Return the most recent detections as a list of tuples."""
    with _lock:
        conn = _get_conn()
        try:
            cur = conn.execute("""
                SELECT id, timestamp, disease, confidence, severity, crop,
                       gps_lat, gps_lng, zone, soil_moisture,
                       temperature, humidity, ai_analysis
                FROM detections
                ORDER BY id DESC
                LIMIT ?
            """, (limit,))
            return cur.fetchall()
        finally:
            conn.close()


def get_zone_memory() -> list:
    """Return all zone records."""
    with _lock:
        conn = _get_conn()
        try:
            cur = conn.execute("SELECT * FROM zone_memory ORDER BY last_visit DESC")
            return cur.fetchall()
        finally:
            conn.close()


def clear_database() -> None:
    """Delete all records from all tables."""
    with _lock:
        conn = _get_conn()
        try:
            conn.executescript("""
                DELETE FROM detections;
                DELETE FROM soil_logs;
                DELETE FROM zone_memory;
            """)
            conn.commit()
        finally:
            conn.close()
    print("[database] All records cleared.")
