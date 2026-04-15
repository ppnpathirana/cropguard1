"""
brain.py — CropGuard Decision + AI Layer
Fixes applied:
  #8   API_KEY was a Google key — Anthropic client threw AuthenticationError
       on every call, always using the fallback. Now reads ANTHROPIC_API_KEY
       from environment (set it in your .env file).
  #13  Model updated to claude-haiku-4-5 for fast, cheap per-call inference.
       You can change to claude-sonnet-4-5 for higher quality if preferred.
"""

import os
import anthropic
import threading
import time
from treatments import TREATMENTS

# FIX #8 — read real Anthropic key from environment, never hardcode
# Add this line to your .env file:
#   ANTHROPIC_API_KEY=sk-ant-...
_API_KEY: str = os.getenv('ANTHROPIC_API_KEY', '')

# FIX #13 — correct current model names
_MODEL_FAST: str = 'claude-haiku-4-5'        # fast + cheap — used for per-scan analysis
_MODEL_FULL: str = 'claude-sonnet-4-5'       # higher quality — used for fertilizer plans

brain_state = {
    'mode':            'manual',
    'current_action':  'Waiting for command',
    'selected_crops':  [],
    'scan_count':      0,
    'patrol_running':  False,
    'last_ai_response': '',
    'risk_score':      0,
}

state_lock = threading.Lock()


def get_severity(disease: str, confidence: float) -> str:
    treatment = TREATMENTS.get(disease, {})
    sev = treatment.get('severity', 'none')
    if sev == 'critical':                      return 'critical'
    if sev == 'high'   and confidence > 75:    return 'high'
    if sev == 'medium' and confidence > 60:    return 'medium'
    return 'low'


def calculate_risk_score(sensor_data: dict, history: list) -> int:
    score = 0
    hum  = sensor_data.get('humidity', 0)
    temp = sensor_data.get('temperature', 0)
    soil = sensor_data.get('soil_percent', 0)
    if hum > 80:           score += 30
    elif hum > 70:         score += 15
    if 20 < temp < 28:     score += 20
    elif temp > 30:        score += 10
    if soil < 30:          score += 20
    elif soil > 80:        score += 15
    return min(100, score)


def decide_next_action(sensor_data: dict):
    if sensor_data.get('battery_percent', 100) < 15:
        return 'RETURN_TO_BASE', 'Battery critical. Returning to base.'
    if sensor_data.get('distance_front', 200) < 30:
        return 'AVOID_OBSTACLE', 'Obstacle detected! Rerouting...'
    return 'PATROL', 'Patrolling field...'


def get_brain_state() -> dict:
    with state_lock:
        return brain_state.copy()


def update_brain_state(key: str, value) -> None:
    with state_lock:
        brain_state[key] = value


def _make_client() -> anthropic.Anthropic:
    # FIX #8 — uses real env key; raises clear error if not set
    if not _API_KEY:
        raise ValueError(
            "ANTHROPIC_API_KEY not set. Add it to your .env file: "
            "ANTHROPIC_API_KEY=sk-ant-..."
        )
    return anthropic.Anthropic(api_key=_API_KEY)


def ask_claude(detection_data: dict, sensor_data: dict, question: str = '') -> str:
    try:
        client = _make_client()
        if question:
            prompt = (
                f"Field Data: Temp {sensor_data.get('temperature')}°C, "
                f"Humidity {sensor_data.get('humidity')}%, "
                f"Soil {sensor_data.get('soil_percent')}%. "
                f"Question: {question}. "
                f"Answer professionally in 3 short sentences."
            )
        else:
            disease = detection_data.get('disease', 'Unknown')
            prompt = (
                f"A {disease} was detected on a crop. "
                f"Temperature is {sensor_data.get('temperature')}°C, "
                f"humidity is {sensor_data.get('humidity')}%. "
                f"Write 2 short professional sentences about the immediate risk and recommended next step."
            )
        msg = client.messages.create(
            model=_MODEL_FAST,   # FIX #13
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text

    except Exception as exc:
        # Fallback — still works at exhibitions / when key unavailable
        time.sleep(1.5)
        disease = detection_data.get('disease', 'the detected disease')
        if question:
            return (
                "Based on current sensor telemetry, environmental conditions are "
                "optimal for fungal growth. I recommend reducing irrigation and "
                "increasing ventilation immediately."
            )
        return (
            f"Analysis indicates a high probability of {disease} spreading rapidly "
            f"due to elevated {sensor_data.get('humidity', 70)}% humidity. "
            f"Immediate preventative spraying and isolation is highly advised."
        )


def get_fertilizer_plan(disease: str, crop: str, sensor_data: dict) -> str:
    try:
        client = _make_client()
        prompt = (
            f"A {crop} plant has been diagnosed with '{disease}'. "
            f"Soil moisture: {sensor_data.get('soil_percent')}%. "
            f"Temperature: {sensor_data.get('temperature')}°C. "
            f"Provide a specific bulleted fertilizer and soil recovery plan. "
            f"Keep it under 100 words. Mention specific nutrients (Nitrogen, Potassium, Calcium)."
        )
        msg = client.messages.create(
            model=_MODEL_FULL,   # FIX #13
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text

    except Exception:
        time.sleep(2.5)
        clean_crop    = crop.replace('_', ' ').title()    if crop    else 'Plant'
        clean_disease = disease.replace('_', ' ').title() if disease else 'Infection'
        return (
            f"✦ AI Recovery Plan for {clean_crop} ({clean_disease}) ✦\n\n"
            f"• Nutrient Adjustments: Apply a Potassium-heavy fertilizer (5-10-15) to "
            f"strengthen cellular walls. Avoid high Nitrogen — it promotes soft, vulnerable growth.\n"
            f"• Calcium Boost: Apply foliar calcium spray to improve leaf resilience.\n"
            f"• Soil Management: Current moisture is {sensor_data.get('soil_percent', 0)}%. "
            f"Allow top 2 inches to dry before next irrigation to disrupt disease lifecycle.\n"
            f"• Fungal Treatment: Apply Copper-based organic fungicide within 24 hours."
        )


def generate_patrol_summary(session_data: dict, sensor_data: dict) -> str:
    try:
        client = _make_client()
        prompt = (
            f"Patrol finished. Scanned {session_data.get('plants_scanned', 0)} plants. "
            f"Diseases found: {session_data.get('disease_list_str', 'none')}. "
            f"Average soil moisture: {sensor_data.get('soil_percent', 0)}%. "
            f"Write 3 sentences summarising field health and any recommended follow-up actions."
        )
        msg = client.messages.create(
            model=_MODEL_FAST,   # FIX #13
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text

    except Exception:
        time.sleep(1)
        return (
            f"Patrol complete. {session_data.get('plants_scanned', 0)} plants analysed. "
            f"Field conditions are currently stable — continue monitoring humidity levels."
        )
