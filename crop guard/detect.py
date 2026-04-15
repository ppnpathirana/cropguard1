import cv2
import numpy as np

# 1. Load the model using OpenCV's DNN module
model_path = r"C:\Users\prime\Desktop\cropguard\best.tflite"
net = cv2.dnn.readNetFromTFLite(model_path)

# 2. Start Camera
cap = cv2.VideoCapture(0)

print("Running using OpenCV DNN Engine. Press 'q' to quit.")

while cap.isOpened():
    ret, frame = cap.read()
    if not ret: break

    # YOLOv5 TFLite usually needs 640x640
    # Create a 'blob' (a special image format for the AI)
    blob = cv2.dnn.blobFromImage(frame, 1/255.0, (640, 640), swapRB=True, crop=False)
    
    # Run the model
    net.setInput(blob)
    output = net.forward() # This is the "Inference" step

    # 3. Process the results
    # Output shape is typically [1, 25200, 85]
    detections = output[0]
    rows = detections.shape[0]

    img_width, img_height = frame.shape[1], frame.shape[0]
    x_factor = img_width / 640
    y_factor = img_height / 640

    for i in range(rows):
        row = detections[i]
        confidence = row[4]
        if confidence > 0.5:
            classes_scores = row[5:]
            class_id = np.argmax(classes_scores)
            
            # Get coordinates
            x, y, w, h = row[0], row[1], row[2], row[3]
            
            left = int((x - 0.5 * w) * x_factor)
            top = int((y - 0.5 * h) * y_factor)
            width = int(w * x_factor)
            height = int(h * y_factor)

            # Draw
            cv2.rectangle(frame, (left, top), (left + width, top + height), (0, 255, 0), 2)
            cv2.putText(frame, f"Object {confidence:.2f}", (left, top - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    cv2.imshow('CropGuard OpenCV Engine', frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()