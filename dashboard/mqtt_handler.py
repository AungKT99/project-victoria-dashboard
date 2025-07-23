"""
MQTT handler for Project Victoria Dashboard
Handles AWS IoT Core communication and data processing
"""
import json
import logging
import threading
import time
from datetime import datetime
from typing import Dict, Callable, Optional
import queue

try:
    from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
    AWS_IOT_AVAILABLE = True
except ImportError:
    AWS_IOT_AVAILABLE = False
    logging.warning("AWSIoTPythonSDK not available, using mock MQTT client")

from config import config
from trilateration import RSSITrilaterationSolver, PositionFilter

class MockMQTTClient:
    """Mock MQTT client for testing without AWS IoT"""
    
    def __init__(self):
        self.connected = False
        self.callbacks = {}
    
    def configureEndpoint(self, endpoint, port):
        pass
    
    def configureCredentials(self, ca_path, key_path, cert_path):
        pass
    
    def configureAutoReconnectBackoffTime(self, base, max_time, stable):
        pass
    
    def configureOfflinePublishQueueing(self, queue_size):
        pass
    
    def configureDrainingFrequency(self, frequency):
        pass
    
    def configureConnectDisconnectTimeout(self, timeout):
        pass
    
    def configureMQTTOperationTimeout(self, timeout):
        pass
    
    def connect(self):
        self.connected = True
        return True
    
    def disconnect(self):
        self.connected = False
    
    def subscribe(self, topic, qos, callback):
        self.callbacks[topic] = callback
    
    def publish(self, topic, payload, qos):
        pass

class MQTTHandler:
    """
    Handles MQTT communication with AWS IoT Core for Project Victoria
    """
    
    def __init__(self, data_callback: Optional[Callable] = None, demo_mode: bool = False):
        self.data_callback = data_callback
        self.demo_mode = demo_mode
        self.client = None
        self.connected = False
        self.running = False
        self.thread = None
        self.data_queue = queue.Queue()
        
        # Initialize trilateration solver and filter
        self.trilateration_solver = RSSITrilaterationSolver()
        self.position_filter = PositionFilter()
        
        # Data storage
        self.latest_rssi_data = {}
        self.latest_position = None
        self.position_history = []
        
        self._setup_logging()
    
    def _setup_logging(self):
        """Setup logging for MQTT handler"""
        self.logger = logging.getLogger('MQTTHandler')
        self.logger.setLevel(logging.INFO)
        
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def _create_client(self):
        """Create and configure MQTT client"""
        if self.demo_mode or not AWS_IOT_AVAILABLE:
            self.client = MockMQTTClient()
            self.logger.info("Using mock MQTT client for demo mode")
        else:
            self.client = AWSIoTMQTTClient(config.aws_iot.client_id)
            
            # Configure connection
            self.client.configureEndpoint(config.aws_iot.endpoint, 8883)
            self.client.configureCredentials(
                config.aws_iot.root_ca_path,
                config.aws_iot.private_key_path,
                config.aws_iot.certificate_path
            )
            
            # Configure connection parameters
            self.client.configureAutoReconnectBackoffTime(1, 32, 20)
            self.client.configureOfflinePublishQueueing(-1)  # Infinite offline publish queueing
            self.client.configureDrainingFrequency(2)  # Draining: 2 Hz
            self.client.configureConnectDisconnectTimeout(10)  # 10 sec
            self.client.configureMQTTOperationTimeout(5)  # 5 sec
    
    def _on_rssi_message(self, client, userdata, message):
        """Callback for RSSI data messages"""
        try:
            payload = json.loads(message.payload.decode('utf-8'))
            self.logger.debug(f"Received RSSI data: {payload}")
            
            # Expected payload format:
            # {
            #     "rsu_id": "RSU1",
            #     "obu_id": "OBU001",
            #     "rssi": -70,
            #     "timestamp": "2024-07-17T15:30:45.123Z",
            #     "rsu_position": {"x": 10.0, "y": 10.0}
            # }
            
            if 'rsu_id' in payload and 'rssi' in payload:
                self.latest_rssi_data[payload['rsu_id']] = {
                    'rssi': payload['rssi'],
                    'timestamp': payload.get('timestamp', datetime.now().isoformat()),
                    'obu_id': payload.get('obu_id', 'unknown')
                }
                
                # Trigger position calculation if we have enough data
                if len(self.latest_rssi_data) >= 3:
                    self._calculate_position()
                
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to decode RSSI message: {e}")
        except Exception as e:
            self.logger.error(f"Error processing RSSI message: {e}")
    
    def _calculate_position(self):
        """Calculate OBU position from latest RSSI data"""
        try:
            # Extract RSSI values
            rssi_measurements = {}
            for rsu_id, data in self.latest_rssi_data.items():
                rssi_measurements[rsu_id] = data['rssi']
            
            # Calculate position using trilateration
            result = self.trilateration_solver.calculate_position(
                config.field.rsu_positions,
                rssi_measurements,
                method='least_squares'
            )
            
            if result:
                x, y, accuracy = result
                
                # Apply position filter
                current_time = time.time()
                filtered_position = self.position_filter.update((x, y), current_time)
                
                position_data = {
                    'x': filtered_position[0],
                    'y': filtered_position[1],
                    'accuracy': accuracy,
                    'timestamp': datetime.now().isoformat(),
                    'rssi_data': dict(self.latest_rssi_data)
                }
                
                self.latest_position = position_data
                self.position_history.append(position_data)
                
                # Limit history size
                if len(self.position_history) > config.dashboard.max_trail_points:
                    self.position_history = self.position_history[-config.dashboard.max_trail_points:]
                
                # Call data callback if provided
                if self.data_callback:
                    self.data_callback(position_data)
                
                self.logger.info(f"Position calculated: ({x:.2f}, {y:.2f}) ±{accuracy:.2f}m")
                
        except Exception as e:
            self.logger.error(f"Error calculating position: {e}")
    
    def connect(self) -> bool:
        """Connect to AWS IoT Core"""
        try:
            if not self.client:
                self._create_client()
            
            result = self.client.connect()
            if result:
                self.connected = True
                
                # Subscribe to RSSI data topic
                rssi_topic = f"{config.aws_iot.topic_prefix}/rssi/+"
                self.client.subscribe(rssi_topic, 1, self._on_rssi_message)
                
                self.logger.info(f"Connected to AWS IoT and subscribed to {rssi_topic}")
                return True
            else:
                self.logger.error("Failed to connect to AWS IoT")
                return False
                
        except Exception as e:
            self.logger.error(f"Connection error: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from AWS IoT Core"""
        if self.client and self.connected:
            self.client.disconnect()
            self.connected = False
            self.logger.info("Disconnected from AWS IoT")
    
    def start_background_processing(self):
        """Start background processing thread"""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._background_loop, daemon=True)
            self.thread.start()
            self.logger.info(f"Started background processing - Demo mode: {self.demo_mode}")
            
            # Immediate simulation for demo mode
            if self.demo_mode:
                self.logger.info("Running immediate demo simulation")
                self._simulate_rssi_data()
    
    def stop_background_processing(self):
        """Stop background processing thread"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
            self.logger.info("Stopped background processing")
    
    def _background_loop(self):
        """Background processing loop"""
        while self.running:
            try:
                # Simulate RSSI data for demo purposes if using mock client
                if self.demo_mode or isinstance(self.client, MockMQTTClient):
                    self._simulate_rssi_data()
                
                time.sleep(config.dashboard.update_interval)
                
            except Exception as e:
                self.logger.error(f"Error in background loop: {e}")
    
    def _simulate_rssi_data(self):
        """Simulate RSSI data for demo purposes"""
        import random
        import math
        
        # Simple geometric simulation - no complex RSSI model
        current_time = time.time()
        
        # Circular motion pattern within field bounds
        angle = (current_time * 0.1) % (2 * math.pi)
        field_width = config.field.width
        field_height = config.field.height
        center_x, center_y = field_width / 2, field_height / 2
        radius = min(field_width, field_height) * 0.2
        
        # TRUE OBU position (what we want to show)
        true_x = center_x + radius * math.cos(angle)
        true_y = center_y + radius * math.sin(angle)
        
        # Create fake but consistent position data directly
        position_data = {
            'x': true_x,
            'y': true_y,
            'accuracy': random.uniform(1.0, 3.0),  # Realistic accuracy
            'timestamp': datetime.now().isoformat(),
            'rssi_data': {}
        }
        
        # Generate fake RSSI values for display only
        for rsu_id, (rsu_x, rsu_y) in config.field.rsu_positions.items():
            distance = math.sqrt((true_x - rsu_x)**2 + (true_y - rsu_y)**2)
            # Simple fake RSSI based on distance (for display only)
            fake_rssi = -40 - (distance * 0.5) + random.gauss(0, 2)
            
            self.latest_rssi_data[rsu_id] = {
                'rssi': fake_rssi,
                'timestamp': datetime.now().isoformat(),
                'obu_id': 'OBU_DEMO'
            }
            position_data['rssi_data'][rsu_id] = self.latest_rssi_data[rsu_id]
        
    def _simulate_rssi_data(self):
        """Simulate RSSI data for demo purposes"""
        import random
        import math
        
        # Simulate an OBU moving in a simple pattern
        current_time = time.time()
        
        # Circular motion pattern within field bounds
        angle = (current_time * 0.1) % (2 * math.pi)
        field_width = config.field.width
        field_height = config.field.height
        center_x, center_y = field_width / 2, field_height / 2
        radius = min(field_width, field_height) * 0.2
        
        true_x = center_x + radius * math.cos(angle)
        true_y = center_y + radius * math.sin(angle)
        
        print(f"DEBUG: Simulated TRUE position: ({true_x:.2f}, {true_y:.2f})")
        
        # Simulate RSSI measurements based on distance to each RSU
        for rsu_id, (rsu_x, rsu_y) in config.field.rsu_positions.items():
            distance = math.sqrt((true_x - rsu_x)**2 + (true_y - rsu_y)**2)
            
            # Convert distance to RSSI with some noise
            true_rssi = self.trilateration_solver.tx_power - 10 * self.trilateration_solver.path_loss_exponent * math.log10(distance)
            noisy_rssi = true_rssi + random.gauss(0, 3)  # 3 dB noise
            
            print(f"DEBUG: {rsu_id} at ({rsu_x}, {rsu_y}) - distance: {distance:.2f}m, RSSI: {noisy_rssi:.1f} dBm")
            
            self.latest_rssi_data[rsu_id] = {
                'rssi': noisy_rssi,
                'timestamp': datetime.now().isoformat(),
                'obu_id': 'OBU_DEMO'
            }
        
        # Trigger position calculation
        if len(self.latest_rssi_data) >= 3:
            self._calculate_position()
            
            # Convert distance to RSSI with some noise
            true_rssi = self.trilateration_solver.tx_power - 10 * self.trilateration_solver.path_loss_exponent * math.log10(distance)
            noisy_rssi = true_rssi + random.gauss(0, 3)  # 3 dB noise
            
            self.latest_rssi_data[rsu_id] = {
                'rssi': noisy_rssi,
                'timestamp': datetime.now().isoformat(),
                'obu_id': 'OBU_DEMO'
            }
        
        # Trigger position calculation
        if len(self.latest_rssi_data) >= 3:
            self._calculate_position()
    
    def get_latest_data(self) -> Dict:
        """Get latest position and RSSI data"""
        return {
            'position': self.latest_position,
            'rssi_data': dict(self.latest_rssi_data),
            'position_history': list(self.position_history),
            'connected': self.connected
        }
    
    def clear_history(self):
        """Clear position history"""
        self.position_history.clear()
        self.logger.info("Position history cleared")
    
    def get_connection_status(self) -> Dict:
        """Get connection status information"""
        if self.demo_mode:
            client_type = "Demo Mode"
            endpoint = "simulated"
        else:
            client_type = 'AWS IoT' if AWS_IOT_AVAILABLE and not isinstance(self.client, MockMQTTClient) else 'Mock'
            endpoint = config.aws_iot.endpoint if AWS_IOT_AVAILABLE and not isinstance(self.client, MockMQTTClient) else 'localhost'
        
        return {
            'connected': self.connected,
            'client_type': client_type,
            'endpoint': endpoint,
            'last_update': self.latest_position['timestamp'] if self.latest_position else None,
            'data_points': len(self.position_history)
        }