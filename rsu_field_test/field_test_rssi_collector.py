#!/usr/bin/env python3
"""
Project Victoria Field Test RSSI Collector
Collects RSSI measurements from RSU socket connection for field testing
"""

import json
import socket
import threading
import time
import signal
import sys
import csv
import argparse
from datetime import datetime, timezone
from pathlib import Path

# Configuration
SOCKET_PORT = 9999





class FieldTestCollector:
    """RSSI data collector for field testing"""

    def __init__(self, distance: float = 0.0, max_samples: int = None):
        self.distance = distance
        self.max_samples = max_samples
        self.sample_count = 0
        self.socket_server = None
        self.running = False
        self.csv_file = None
        self.csv_writer = None
        
        # Setup signal handlers for proper cleanup
        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)

        # Initialize CSV file
        self.init_csv_file()

        print(f"Field Test RSSI Collector initialized")
        print(f"Distance: {self.distance}m")
        if max_samples:
            print(f"Max samples: {max_samples}")
        else:
            print("Running continuously until Ctrl+C")

    def init_csv_file(self):
        """Initialize CSV file with headers"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"rssi_field_test_{timestamp}.csv"
        
        try:
            self.csv_file = open(filename, 'w', newline='')
            self.csv_writer = csv.writer(self.csv_file)
            
            # Write header
            self.csv_writer.writerow(['timestamp', 'rssi_dbm', 'distance_m'])
            self.csv_file.flush()
            
            print(f"CSV file created: {filename}")
            
        except Exception as e:
            print(f"Failed to create CSV file: {e}")
            sys.exit(1)

    def start_socket_server(self):
        """Start socket server for RSU connections"""
        try:
            self.socket_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket_server.bind(("localhost", SOCKET_PORT))
            self.socket_server.listen(5)

            print(f"Socket server listening on port {SOCKET_PORT}")

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
        """Process RSSI data from RSU and save to CSV"""
        try:
            rsu_data = json.loads(data.strip())

            # Extract RSSI and timestamp
            rssi_value = float(rsu_data.get("rssi", 0))
            timestamp = rsu_data.get("timestamp", datetime.now(timezone.utc).isoformat())

            # Write to CSV
            self.csv_writer.writerow([
                timestamp,
                rssi_value,
                self.distance
            ])
            self.csv_file.flush()

            self.sample_count += 1
            print(f"Sample {self.sample_count}: RSSI {rssi_value} dBm at {self.distance}m")

            # Check if we've reached max samples
            if self.max_samples and self.sample_count >= self.max_samples:
                print(f"Reached maximum samples ({self.max_samples}). Stopping...")
                self.stop()

        except json.JSONDecodeError as e:
            print(f"Failed to parse JSON data: {e}")
        except Exception as e:
            print(f"Failed to process RSU data: {e}")

    def start(self):
        """Start the collector"""
        print("Starting Field Test RSSI Collector...")

        self.running = True

        # Start socket server
        if not self.start_socket_server():
            return False

        print("Field Test Collector started successfully")
        print("Waiting for RSU connections and RSSI data...")
        return True

    def stop(self):
        """Stop the collector"""
        print("Stopping Field Test Collector...")

        self.running = False

        # Close socket
        if self.socket_server:
            self.socket_server.close()
            print("Socket server closed")

        # Close CSV file
        if self.csv_file:
            self.csv_file.close()
            print(f"CSV file saved with {self.sample_count} samples")

        print("Field Test Collector stopped")

    def shutdown(self, signum, frame):
        """Handle shutdown signals for proper cleanup"""
        print(f"\nReceived signal {signum}, shutting down...")
        self.stop()
        sys.exit(0)

    def run(self):
        """Run the collector"""
        if not self.start():
            print("Failed to start collector")
            return

        try:
            print("Collector running... Press Ctrl+C to stop")
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nInterrupted by user")
        finally:
            self.stop()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Project Victoria Field Test RSSI Collector')
    parser.add_argument('--distance', '-d', type=float, required=True,
                       help='Distance in meters for this measurement session')
    parser.add_argument('--samples', '-s', type=int, default=None,
                       help='Maximum number of samples to collect (default: unlimited)')

    args = parser.parse_args()

    if args.distance < 0:
        print("Error: Distance must be non-negative")
        sys.exit(1)

    if args.samples is not None and args.samples <= 0:
        print("Error: Number of samples must be positive")
        sys.exit(1)

    collector = FieldTestCollector(
        distance=args.distance,
        max_samples=args.samples
    )
    collector.run()


if __name__ == "__main__":
    main()