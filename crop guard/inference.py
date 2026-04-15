import cv2
import numpy as np
import threading
import time
import os
from collections import Counter
from treatments import CLASS_NAMES

MODEL_PATH = os.getenv('MODEL_PATH', 'best.tflite')
MODEL_LOADED = False
interpreter = None
input_details = None
output_details = None
input_shape = None
model_num_classes = 0

CURRENT_CROP_FILTER = ""
interpreter_lock = threading.Lock()

try:
    import tflite_runtime.interpreter as tflite
    interpreter = tflite.Interpreter(model_path=MODEL_PATH)
    interpreter.allocate_tensors()
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()
    input_shape = input_details[0]['shape']
    model_num_classes = output_details[0]['shape'][-1]
    MODEL_LOADED = True
    print(f"TFLite runtime loaded: {MODEL_PATH}")
except Exception:
    try:
        import tensorflow as tf
        interpreter = tf.lite.Interpreter(model_path=MODEL_PATH)
        interpreter.allocate_tensors()
        input_details = interpreter.get_input_details()
        output_details = interpreter.get_output_details()
        input_shape = input_details[0]['shape']
        model_num_classes = output_details[0]['shape'][-1]
        MODEL_LOADED = True
        print(f"TensorFlow lite loaded: {MODEL_PATH}")
    except Exception as e:
        print(f"Model not loaded: {e}")

camera = None
camera_running = False
latest_frame = None
latest_jpeg = b''
current_detection = None

def set_crop_filter(crop_name):
    global CURRENT_CROP_FILTER
    if crop_name and crop_name.strip() != "":
        CURRENT_CROP_FILTER = crop_name.strip().lower()
        print(f"Crop filter activated: Only detecting '{CURRENT_CROP_FILTER}'")
    else:
        CURRENT_CROP_FILTER = ""
        print("Crop filter cleared: Detecting all crops")

def init_camera(index=0):
    global camera, camera_running
    try:
        camera = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if not camera.isOpened():
            camera = cv2.VideoCapture(index)
            
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        camera.set(cv2.CAP_PROP_FPS, 30)
        camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        if camera.isOpened():
            camera_running = True
            return True
        return False
    except Exception as e:
        print(f"Camera error: {e}")
        return False

def camera_loop():
    global latest_frame, latest_jpeg
    
    while camera_running:
        if camera and camera.isOpened():
            ret, frame = camera.read()
            if ret:
                latest_frame = frame 
                annotated = frame.copy()
                det = current_detection
                if det is not None:
                    cls, conf, bbox = det
                    x1, y1, x2, y2 = bbox
                    cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    
                    label = f"{cls} {conf}%"
                    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
                    bg_y1 = max(0, y1 - th - 10)
                    cv2.rectangle(annotated, (x1, bg_y1), (x1 + tw, bg_y1 + th + 10), (0, 255, 0), -1)
                    cv2.putText(annotated, label, (x1, bg_y1 + th + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
                
                ret2, buffer = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 50])
                if ret2:
                    latest_jpeg = buffer.tobytes()
        
        time.sleep(0.01)

def ai_loop():
    global current_detection
    while camera_running:
        if latest_frame is not None:
            frame_to_infer = latest_frame.copy() 
            cls, conf, bbox = run_yolo_inference(frame_to_infer)
            
            if cls and bbox:
                current_detection = (cls, conf, bbox)
            else:
                current_detection = None
                
        time.sleep(0.06) 

def preprocess_frame(frame):
    h, w = input_shape[1], input_shape[2]
    resized = cv2.resize(frame, (w, h))
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
    normalized = rgb.astype(np.float32) / 255.0
    return np.expand_dims(normalized, axis=0)

def run_yolo_inference(frame):
    if not MODEL_LOADED or interpreter is None:
        return None, 0, None

    with interpreter_lock:
        try:
            input_data = preprocess_frame(frame)
            interpreter.set_tensor(input_details[0]['index'], input_data)
            interpreter.invoke()
            
            output = interpreter.get_tensor(output_details[0]['index'])[0]

            if len(output.shape) == 2:
                if output.shape[1] > output.shape[0]:
                    output = output.transpose()

                bboxes = output[:, :4]

                if output.shape[1] == len(CLASS_NAMES) + 4:
                    class_scores = output[:, 4:]
                elif output.shape[1] == len(CLASS_NAMES) + 5:
                    objectness = output[:, 4:5]
                    raw_classes = output[:, 5:]
                    class_scores = raw_classes * objectness
                else:
                    return None, 0, None

                if CURRENT_CROP_FILTER:
                    mask = np.zeros(len(CLASS_NAMES))
                    has_match = False
                    for i, name in enumerate(CLASS_NAMES):
                        if CURRENT_CROP_FILTER in name.lower():
                            mask[i] = 1.0
                            has_match = True
                    if has_match:
                        class_scores = class_scores * mask

                max_scores = np.max(class_scores, axis=1)
                best_box_idx = np.argmax(max_scores)

                class_id = int(np.argmax(class_scores[best_box_idx]))
                confidence = float(max_scores[best_box_idx]) * 100

                # --- FIX: INCREASED THRESHOLD TO 45 ---
                if confidence < 45 or class_id < 0 or class_id >= len(CLASS_NAMES):
                    return None, 0, None

                best_class_name = CLASS_NAMES[class_id]

                h, w, _ = frame.shape
                model_h, model_w = input_shape[1], input_shape[2]
                
                x_c, y_c, bw, bh = bboxes[best_box_idx]
                x_c = (x_c / model_w) * w
                y_c = (y_c / model_h) * h
                bw = (bw / model_w) * w
                bh = (bh / model_h) * h
                
                x1 = max(0, int(x_c - bw / 2))
                y1 = max(0, int(y_c - bh / 2))
                x2 = min(w, int(x_c + bw / 2))
                y2 = min(h, int(y_c + bh / 2))
                
                return best_class_name, round(confidence, 1), (x1, y1, x2, y2)

            else:
                class_id = int(np.argmax(output))
                confidence = float(np.max(output)) * 100
                
                # --- FIX: INCREASED THRESHOLD TO 45 ---
                if confidence < 45 or class_id < 0 or class_id >= len(CLASS_NAMES):
                    return None, 0, None
                return CLASS_NAMES[class_id], round(confidence, 1), None

        except Exception as e:
            return None, 0, None

def generate_mjpeg():
    while True:
        if latest_jpeg:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n'
                   + latest_jpeg + b'\r\n')
        time.sleep(0.033)

def get_latest_frame():
    if latest_frame is not None:
        return latest_frame.copy()
    return None

def predict_single(frame):
    cls, conf, bbox = run_yolo_inference(frame)
    return cls, conf

def predict_multi_frame(num_frames=3):
    results = []
    for _ in range(num_frames):
        frame = get_latest_frame()
        if frame is not None:
            disease, conf = predict_single(frame)
            
            # --- FIX: INCREASED THRESHOLD TO 45 ---
            if disease and conf > 45:
                results.append((disease, conf))
        time.sleep(0.1)
    
    if not results:
        return None, 0
        
    diseases = [r[0] for r in results]
    counter = Counter(diseases)
    most_common = counter.most_common(1)[0][0]
    matching = [r[1] for r in results if r[0] == most_common]
    avg_conf = round(sum(matching) / len(matching), 1)
    
    return most_common, avg_conf

def save_detection_image(frame, disease, timestamp):
    folder = 'data/images'
    os.makedirs(folder, exist_ok=True)
    safe_name = disease.replace(' ', '_').replace('/', '_')
    filename = f"{folder}/{timestamp}_{safe_name}.jpg"
    cv2.imwrite(filename, frame)
    return filename

def start_camera():
    if init_camera():
        threading.Thread(target=camera_loop, daemon=True).start()
        threading.Thread(target=ai_loop, daemon=True).start()
        return True
    return False

def stop_camera():
    global camera_running
    camera_running = False
    if camera:
        camera.release()