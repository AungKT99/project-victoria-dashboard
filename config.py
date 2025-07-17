"""
Configuration management for Project Victoria Dashboard
"""
import os
from dataclasses import dataclass
from typing import Dict, Tuple

@dataclass
class AWSIoTConfig:
    """AWS IoT configuration"""
    endpoint: str = "your-iot-endpoint.amazonaws.com"
    root_ca_path: str = "certs/root-CA.crt"
    certificate_path: str = "certs/certificate.pem.crt"
    private_key_path: str = "certs/private.pem.key"
    client_id: str = "project-victoria-dashboard"
    topic_prefix: str = "project-victoria"

@dataclass
class FieldConfig:
    """Field configuration for the construction site"""
    width: float = 100.0  # meters
    height: float = 75.0  # meters
    rsu_positions: Dict[str, Tuple[float, float]] = None
    
    def __post_init__(self):
        if self.rsu_positions is None:
            self.rsu_positions = {
                "RSU1": (10.0, 10.0),
                "RSU2": (90.0, 10.0),
                "RSU3": (50.0, 65.0)
            }

@dataclass
class DashboardConfig:
    """Dashboard configuration"""
    update_interval: float = 0.1  # seconds (10 Hz)
    max_trail_points: int = 100
    rssi_threshold: float = -90.0  # dBm
    position_accuracy_threshold: float = 5.0  # meters

class Config:
    """Main configuration class"""
    
    def __init__(self):
        self.aws_iot = AWSIoTConfig()
        self.field = FieldConfig()
        self.dashboard = DashboardConfig()
        
        # Load from environment variables if available
        self._load_from_env()
    
    def _load_from_env(self):
        """Load configuration from environment variables"""
        if os.getenv('AWS_IOT_ENDPOINT'):
            self.aws_iot.endpoint = os.getenv('AWS_IOT_ENDPOINT')
        
        if os.getenv('AWS_IOT_CLIENT_ID'):
            self.aws_iot.client_id = os.getenv('AWS_IOT_CLIENT_ID')
        
        if os.getenv('FIELD_WIDTH'):
            self.field.width = float(os.getenv('FIELD_WIDTH'))
        
        if os.getenv('FIELD_HEIGHT'):
            self.field.height = float(os.getenv('FIELD_HEIGHT'))

# Global configuration instance
config = Config()