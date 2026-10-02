# CropGuard 🤖🌱

CropGuard is an advanced, autonomous agricultural robot powered by IoT, AI (TensorFlow Lite), and real-time computer vision to monitor crop health, analyze soil conditions, and detect diseases at an early stage. 

Designed for scalability and robust performance in modern farming environments, CropGuard seamlessly integrates hardware control and intelligent software analysis into one cohesive dashboard.

## 🌟 Features
- **Real-Time Video Analytics:** Live MJPEG streaming and onboard TensorFlow Lite object detection.
- **Disease & Health Monitoring:** AI-powered anomaly detection with automated risk scoring.
- **Autonomous & Manual Navigation:** Switch seamlessly between automated patrol routes and manual joystick control.
- **Hardware Integration:** Real-time sensor fusion (temperature, humidity, soil moisture) and servo motor operations.
- **Intuitive Web Dashboard:** A responsive, dark-themed UI built with HTML/CSS, WebSockets (Socket.IO), and Flask.

## 🚀 Getting Started

### Prerequisites
- Python 3.9+
- A working serial port connected to the hardware (Arduino/ESP32).
- Supported Camera (Webcam or Pi Camera).

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/ppnpathirana/cropguard1.git
   cd cropguard1
   ```

2. **Set up a virtual environment (Recommended):**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install the dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Variables:**
   Create a `.env` file in the `src/` directory and set the necessary configurations (e.g., API keys, Secret keys).
   ```bash
   FLASK_SECRET_KEY=your_secure_secret_key
   # If using Anthropic API for AI logic
   ANTHROPIC_API_KEY=your_api_key_here
   ```

### Running the Application

Start the Flask server from the `src` directory:
```bash
cd src
python app.py
```
The application will launch and be accessible at `http://localhost:5000`.

## 📁 Project Structure

```
cropguard1/
├── src/
│   ├── app.py              # Main Flask application and SocketIO server
│   ├── auto_mode.py        # Autonomous navigation logic
│   ├── brain.py            # AI decision making and severity analysis
│   ├── database.py         # SQLite database management
│   ├── detect.py           # Object detection module
│   ├── inference.py        # TFLite inference engine for computer vision
│   ├── sensors.py          # Sensor reading and processing
│   ├── serial_comm.py      # Serial communication with hardware
│   ├── treatments.py       # Disease treatment mappings
│   ├── best.tflite         # Compiled TFLite Model
│   └── templates/
│       └── index.html      # Frontend Web Dashboard
├── requirements.txt        # Python dependencies
├── .gitignore              # Ignored files and folders
└── README.md               # Project documentation
```

## 🛠 Tech Stack
- **Backend:** Python, Flask, Flask-SocketIO, SQLite
- **AI / ML:** TensorFlow Lite, OpenCV
- **Hardware Comms:** PySerial
- **Frontend:** HTML5, CSS3, JavaScript (Socket.IO client)

## 📄 License
This project is for educational and research purposes.