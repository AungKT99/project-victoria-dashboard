# Project Victoria Dashboard

A real-time dashboard for visualizing vehicle and worker localization at construction sites using V2X technology and RSSI-based trilateration.

## 🚧 Project Overview

Project Victoria is a safety system designed to prevent accidents between vehicles and workers at construction sites through:

- **Real-time localization** using RSSI measurements from V2X RSUs
- **AI-based safety alerts** for collision prediction
- **Interactive dashboard** for monitoring and visualization
- **Integration with AWS IoT Core** for cloud-based processing

## 🏗️ System Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   RSU 1,2,3     │    │  Python Bridge  │    │   AWS IoT Core  │
│   (C++ Apps)    │───▶│  (Unix Socket)  │───▶│     (MQTT)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                        │
                                                        ▼
┌─────────────────┐                           ┌─────────────────┐
│ Streamlit App   │◀──────────────────────────│  MQTT Handler   │
│  (Dashboard)    │                           │ (Background)    │
└─────────────────┘                           └─────────────────┘
                                                        │
                                                        ▼
                                              ┌─────────────────┐
                                              │ Trilateration   │
                                              │   Algorithm     │
                                              └─────────────────┘
```

## 📁 File Structure

```
dashboard/
├── app.py                    # Main Streamlit application
├── mqtt_handler.py           # AWS IoT MQTT subscriber
├── trilateration.py          # Position calculation algorithms
├── config.py                 # Configuration management
├── requirements.txt          # Python dependencies
├── start_dashboard.sh        # Startup script
├── README.md                 # This file
└── utils/
    ├── field_config.py       # Field configuration utilities
    └── data_processing.py    # Data processing helpers
```

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- pip package manager
- Git (optional, for cloning)

### Installation

1. **Clone or download the project files**
   ```bash
   # If using git
   git clone <repository-url>
   cd dashboard
   
   # Or download and extract the files
   ```

2. **Install dependencies**
   ```bash
   # Create virtual environment (recommended)
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   
   # Install dependencies
   pip install -r requirements.txt
   ```

3. **Run the dashboard**
   ```bash
   streamlit run app.py
   ```

   The dashboard will be available at `http://localhost:8501`

## 🔧 Configuration

### Field Configuration

The dashboard allows you to configure:

- **Field dimensions** (width × height in meters)
- **RSU positions** (x, y coordinates)
- **Display options** (trail visibility, auto-refresh)

### AWS IoT Integration

To connect to AWS IoT Core:

1. **Create `certs/` directory**
   ```bash
   mkdir certs
   ```

2. **Place AWS IoT certificates**:
   - `certs/root-CA.crt` - Root CA certificate
   - `certs/certificate.pem.crt` - Device certificate
   - `certs/private.pem.key` - Private key

3. **Update configuration** in `config.py`:
   ```python
   @dataclass
   class AWSIoTConfig:
       endpoint: str = "your-iot-endpoint.amazonaws.com"
       # ... other settings
   ```

### Environment Variables

Optional environment variables:

```bash
export AWS_IOT_ENDPOINT="your-endpoint.amazonaws.com"
export AWS_IOT_CLIENT_ID="project-victoria-dashboard"
export FIELD_WIDTH="100"
export FIELD_HEIGHT="75"
```

## 📊 Features

### Real-time Visualization

- **Interactive field map** with RSU and OBU positions
- **Position trail** showing movement history
- **RSSI signal strength** indicators
- **Coverage quality** assessment

### Data Processing

- **Trilateration algorithms** for position calculation
- **Position filtering** using Kalman-like filters
- **Movement statistics** (speed, distance, variance)
- **Data validation** and outlier detection

### Configuration Tools

- **Auto-optimization** of RSU positions
- **Coverage quality** scoring
- **Positioning suggestions** for improved accuracy
- **Field boundary** validation

### Data Export

- **CSV export** of position and RSSI data
- **Real-time metrics** (data rate, accuracy)
- **Historical analysis** tools

## 🛠️ Technical Details

### Trilateration Algorithm

The system uses RSSI-based trilateration with:

- **Log-distance path loss model** for RSSI-to-distance conversion
- **Least squares** and **optimization-based** solvers
- **Geometric Dilution of Precision (GDOP)** calculation
- **Position filtering** for noise reduction

### MQTT Data Format

Expected RSSI data format:
```json
{
    "rsu_id": "RSU1",
    "obu_id": "OBU001",
    "rssi": -70,
    "timestamp": "2024-07-17T15:30:45.123Z",
    "rsu_position": {"x": 10.0, "y": 10.0}
}
```

### Demo Mode

Without AWS IoT certificates, the dashboard runs in demo mode with:
- Simulated OBU movement patterns
- Synthetic RSSI measurements
- Realistic noise and positioning errors

## 🔍 Troubleshooting

### Common Issues

1. **Connection Failed**
   - Check AWS IoT endpoint configuration
   - Verify certificate file paths and permissions
   - Ensure proper AWS IoT policies are attached

2. **No Position Data**
   - Verify at least 3 RSUs are providing RSSI data
   - Check RSSI values are within reasonable range (-30 to -100 dBm)
   - Validate RSU positions are within field boundaries

3. **Poor Accuracy**
   - Optimize RSU positions using the auto-optimization tool
   - Increase number of RSUs for better coverage
   - Check for RSSI measurement noise and interference

### Debug Mode

Enable debug logging by setting:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 📈 Performance

### System Requirements

- **CPU**: 2+ cores recommended
- **RAM**: 2GB minimum, 4GB recommended
- **Network**: Stable internet connection for AWS IoT
- **Browser**: Modern browser with JavaScript enabled

### Optimization Tips

- Adjust `update_interval` in `config.py` for performance vs. responsiveness
- Limit `max_trail_points` for better memory usage
- Use position filtering to reduce noise

