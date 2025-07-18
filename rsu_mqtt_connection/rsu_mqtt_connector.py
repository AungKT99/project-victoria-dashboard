"""
Project Victoria MQTT5 Gateway - Simplified Version
RSU to AWS IoT Cloud Communication Gateway
"""

import json
import socket
import threading
import time
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass, asdict

from awsiot import mqtt5_client_builder
from awscrt import mqtt5


@dataclass
class RSIMessage:
    """RSSI measurement data structure"""
    timestamp: str
    rsu_id: str
    obu_id: str
    rssi_value: float


class ConfigManager:
    """Simple configuration file manager"""

    def __init__(self, config_path: str = "config.json"):
        self.config_path = Path(config_path)
        self.config = {}
        self.load_config()

    def load_config(self):
        """Load configuration from JSON file"""
        if not self.config_path.exists():
            print(f"Configuration file {self.config_path} not found!")
            sys.exit(1)

        try:
            with open(self.config_path, 'r') as f:
                self.config = json.load(f)
            print(f"Configuration loaded from {self.config_path}")
        except Exception as e:
            print(f"Failed to load config: {e}")
            sys.exit(1)


class VictoriaGateway:
    """Simplified MQTT gateway for Project Victoria"""

    def __init__(self, config_path: str = "config.json"):
        self.config = ConfigManager(config_path).config
        self.mqtt_client = None
        self.socket_server = None
        self.running = False
        self.connected = False

        # Setup signal handlers
        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)

        print("Victoria Gateway initialized")

    def create_mqtt_client(self):
        """Create MQTT5 client"""
        aws_config = self.config["aws_iot"]

        try:
            self.mqtt_client = mqtt5_client_builder.mtls_from_path(
                endpoint=aws_config["endpoint"],
                cert_filepath=aws_config["cert_path"],
                pri_key_filepath=aws_config["key_path"],
                ca_filepath=aws_config.get("ca_path"),
                on_lifecycle_connection_success=self.on_connect,
                on_lifecycle_connection_failure=self.on_disconnect
            )
            print("MQTT client created")
            return True
        except Exception as e:
            print(f"Failed to create MQTT client: {e}")
            return False

    def on_connect(self, lifecycle_connect_success_data):
        """MQTT connection success"""
        self.connected = True
        print("MQTT connected")

    def on_disconnect(self, lifecycle_connection_failure):
        """MQTT connection failure"""
        self.connected = False
        print(f"MQTT disconnected: {lifecycle_connection_failure.exception}")

    def start_socket_server(self):
        """Start socket server for RSU connections"""
        port = self.config["socket"]["port"]

        try:
            self.socket_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket_server.bind(("localhost", port))
            self.socket_server.listen(5)

            print(f"Socket server listening on port {port}")

            # Accept connections in background
            threading.Thread(target=self.accept_connections, daemon=True).start()
            return True

        except Exception as e:
            print(f"Failed to start socket server: {e}")
            return False

    def accept_connections(self):
        """Accept RSU connections"""
        while self.running:
            try:
                client_socket, address = self.socket_server.accept()
                print(f"RSU connected from {address}")
                threading.Thread(
                    target=self.handle_rsu,
                    args=(client_socket, address),
                    daemon=True
                ).start()
            except Exception as e:
                if self.running:
                    print(f"Error accepting connection: {e}")
                break

    def handle_rsu(self, client_socket, address):
        """Handle individual RSU connection"""
        try:
            while self.running:
                data = client_socket.recv(4096)
                if not data:
                    break

                self.process_rssi_data(data.decode('utf-8'))

        except Exception as e:
            print(f"Error with RSU {address}: {e}")
        finally:
            client_socket.close()
            print(f"RSU {address} disconnected")

    def process_rssi_data(self, data):
        """Process RSSI data from RSU"""
        try:
            rsu_data = json.loads(data.strip())

            # Create RSSI message
            rssi_msg = RSIMessage(
                timestamp=rsu_data.get("timestamp", datetime.now(timezone.utc).isoformat()),
                rsu_id=rsu_data.get("rsu_id"),
                obu_id=rsu_data.get("obu_id"),
                rssi_value=float(rsu_data.get("rssi"))
            )

            # Send to AWS IoT
            self.send_to_aws(rssi_msg)

        except Exception as e:
            print(f"Failed to process RSU data: {e}")

    def send_to_aws(self, message: RSIMessage):
        """Send message to AWS IoT"""
        if not self.connected:
            print("Cannot send - MQTT not connected")
            return

        try:
            topic = self.config["topic"]
            payload = json.dumps(asdict(message))

            self.mqtt_client.publish(
                publish_packet=mqtt5.PublishPacket(
                    topic=topic,
                    payload=payload.encode('utf-8'),
                    qos=mqtt5.QoS.AT_LEAST_ONCE
                )
            )

            print(f"Sent RSSI data: RSU {message.rsu_id}, OBU {message.obu_id}, RSSI {message.rssi_value}")
            print(f"Published to '{topic}': {payload}") #debugging

        except Exception as e:
            print(f"Failed to send to AWS: {e}")

    def start(self):
        """Start the gateway"""
        print("Starting Victoria Gateway...")

        self.running = True

        # Create and start MQTT client
        if not self.create_mqtt_client():
            return False

        try:
            self.mqtt_client.start()
            print("MQTT client started")
        except Exception as e:
            print(f"Failed to start MQTT: {e}")
            return False

        # Start socket server
        if not self.start_socket_server():
            return False

        print("Victoria Gateway started successfully")
        return True

    def stop(self):
        """Stop the gateway"""
        print("Stopping Victoria Gateway...")

        self.running = False

        # Stop MQTT
        if self.mqtt_client:
            try:
                self.mqtt_client.stop().result(timeout=5)
                print("MQTT stopped")
            except Exception as e:
                print(f"Error stopping MQTT: {e}")

        # Close socket
        if self.socket_server:
            self.socket_server.close()
            print("Socket server closed")

        print("Victoria Gateway stopped")

    def shutdown(self, signum, frame):
        """Handle shutdown signals"""
        print(f"Received signal {signum}, shutting down...")
        self.stop()
        sys.exit(0)

    def run(self):
        """Run the gateway"""
        if not self.start():
            print("Failed to start gateway")
            return

        try:
            print("Gateway running... Press Ctrl+C to stop")
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Interrupted by user")
        finally:
            self.stop()


def main():
    """Main entry point"""
    gateway = VictoriaGateway("mqtt_config.json")
    gateway.run()


if __name__ == "__main__":
    main()