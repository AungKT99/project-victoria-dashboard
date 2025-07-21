"""
Trilateration algorithms for Project Victoria
Calculates OBU position from RSSI measurements from multiple RSUs
"""
import numpy as np
from scipy.optimize import minimize
from typing import Dict, Tuple, Optional, List
import math

class RSSITrilaterationSolver:
    """
    Trilateration solver using RSSI measurements
    """
    
    def __init__(self):
        # RSSI to distance conversion parameters  
        # Using simplified log-distance path loss model: RSSI = A - 10*n*log10(d)
        self.tx_power = 20  # dBm (Murata Type1YL DSRC mode typical power)
        self.path_loss_exponent = 2.0  # Free space = 2, urban = 2.7-5
        self.reference_distance = 1.0  # meters
        
    def rssi_to_distance(self, rssi: float) -> float:
        """
        Convert RSSI to distance using log-distance path loss model
        
        Args:
            rssi: Received Signal Strength Indicator in dBm
            
        Returns:
            Distance in meters
        """
        if rssi >= self.tx_power:
            return self.reference_distance
        
        # RSSI = Tx_Power - 10 * n * log10(d/d0)
        # d = d0 * 10^((Tx_Power - RSSI) / (10 * n))
        distance = self.reference_distance * (10 ** ((self.tx_power - rssi) / (10 * self.path_loss_exponent)))
        
        # Debug logging
        print(f"DEBUG: RSSI {rssi} dBm → Distance {distance:.2f} m")
        
        # Clamp to reasonable values
        return max(0.1, min(distance, 1000.0))
    
    def calculate_position_least_squares(self, 
                                       rsu_positions: Dict[str, Tuple[float, float]], 
                                       rssi_measurements: Dict[str, float]) -> Optional[Tuple[float, float, float]]:
        """
        Calculate OBU position using least squares trilateration
        
        Args:
            rsu_positions: Dictionary mapping RSU ID to (x, y) coordinates
            rssi_measurements: Dictionary mapping RSU ID to RSSI value
            
        Returns:
            Tuple of (x, y, accuracy_estimate) or None if calculation fails
        """
        if len(rssi_measurements) < 3:
            return None
        
        # Convert RSSI to distances
        distances = {}
        rsu_coords = []
        dist_values = []
        
        print(f"\nDEBUG: Starting trilateration")
        print(f"RSU positions: {rsu_positions}")
        print(f"RSSI measurements: {rssi_measurements}")
        
        for rsu_id, rssi in rssi_measurements.items():
            if rsu_id in rsu_positions:
                distance = self.rssi_to_distance(rssi)
                distances[rsu_id] = distance
                rsu_coords.append(rsu_positions[rsu_id])
                dist_values.append(distance)
                print(f"DEBUG: {rsu_id} at {rsu_positions[rsu_id]} → distance {distance:.2f}m")
        
        if len(rsu_coords) < 3:
            print(f"DEBUG: Not enough RSUs ({len(rsu_coords)})")
            return None
        
        rsu_coords = np.array(rsu_coords)
        dist_values = np.array(dist_values)
        
        # Use first RSU as reference point
        ref_point = rsu_coords[0]
        
        # Use a more stable trilateration approach
        # Convert to relative coordinates to avoid large numbers
        x1, y1 = rsu_coords[0]
        r1 = dist_values[0]
        
        # Translate all coordinates relative to first RSU
        A = []
        b = []
        
        for i in range(1, len(rsu_coords)):
            xi, yi = rsu_coords[i]
            ri = dist_values[i]
            
            # Relative coordinates
            dx = xi - x1
            dy = yi - y1
            
            # Linearized equation: 2*dx*x + 2*dy*y = dx² + dy² + r1² - ri²
            A.append([2 * dx, 2 * dy])
            b.append(dx**2 + dy**2 + r1**2 - ri**2)
            
            print(f"DEBUG: Equation {i}: 2*{dx}*x + 2*{dy}*y = {dx**2 + dy**2 + r1**2 - ri**2}")
        
        A = np.array(A)
        b = np.array(b)
        
        print(f"DEBUG: Matrix A = \n{A}")
        print(f"DEBUG: Vector b = {b}")
        
        try:
            # Solve least squares problem
            position_rel, residuals, rank, s = np.linalg.lstsq(A, b, rcond=None)
            
            if len(position_rel) != 2:
                print(f"DEBUG: Least squares failed - wrong dimensions")
                return None
                
            # Convert back to absolute coordinates
            x = position_rel[0] + x1
            y = position_rel[1] + y1
            
            print(f"DEBUG: Relative solution: ({position_rel[0]:.2f}, {position_rel[1]:.2f})")
            print(f"DEBUG: Absolute position: ({x:.2f}, {y:.2f})")
            
            # Calculate accuracy estimate from residuals
            if len(residuals) > 0:
                accuracy = np.sqrt(residuals[0] / len(rsu_coords))
            else:
                # Calculate residuals manually if not returned
                predicted_distances = [np.sqrt((x - rsu_coords[i][0])**2 + (y - rsu_coords[i][1])**2) 
                                     for i in range(len(rsu_coords))]
                residual_sum = sum((predicted_distances[i] - dist_values[i])**2 
                                 for i in range(len(rsu_coords)))
                accuracy = np.sqrt(residual_sum / len(rsu_coords))
            
            print(f"DEBUG: Final result: ({x:.2f}, {y:.2f}) ±{accuracy:.2f}m")
            return (float(x), float(y), float(accuracy))
            
        except np.linalg.LinAlgError:
            return None
    
    def calculate_position_optimization(self,
                                      rsu_positions: Dict[str, Tuple[float, float]], 
                                      rssi_measurements: Dict[str, float],
                                      initial_guess: Tuple[float, float] = None) -> Optional[Tuple[float, float, float]]:
        """
        Calculate OBU position using optimization-based approach
        
        Args:
            rsu_positions: Dictionary mapping RSU ID to (x, y) coordinates
            rssi_measurements: Dictionary mapping RSU ID to RSSI value
            initial_guess: Initial position guess (x, y)
            
        Returns:
            Tuple of (x, y, accuracy_estimate) or None if calculation fails
        """
        if len(rssi_measurements) < 3:
            return None
        
        # Convert RSSI to distances
        valid_data = []
        for rsu_id, rssi in rssi_measurements.items():
            if rsu_id in rsu_positions:
                distance = self.rssi_to_distance(rssi)
                valid_data.append((rsu_positions[rsu_id], distance))
        
        if len(valid_data) < 3:
            return None
        
        # Initial guess (center of RSU positions if not provided)
        if initial_guess is None:
            rsu_coords = [pos for pos, _ in valid_data]
            initial_guess = (
                sum(pos[0] for pos in rsu_coords) / len(rsu_coords),
                sum(pos[1] for pos in rsu_coords) / len(rsu_coords)
            )
        
        def objective_function(pos):
            """Objective function to minimize"""
            x, y = pos
            error = 0
            for (rsu_x, rsu_y), measured_dist in valid_data:
                calculated_dist = math.sqrt((x - rsu_x)**2 + (y - rsu_y)**2)
                error += (calculated_dist - measured_dist)**2
            return error
        
        try:
            result = minimize(objective_function, initial_guess, method='BFGS')
            
            if result.success:
                x, y = result.x
                accuracy = math.sqrt(result.fun / len(valid_data))
                return (float(x), float(y), float(accuracy))
            else:
                return None
                
        except Exception:
            return None
    
    def calculate_position(self, 
                          rsu_positions: Dict[str, Tuple[float, float]], 
                          rssi_measurements: Dict[str, float],
                          method: str = 'least_squares') -> Optional[Tuple[float, float, float]]:
        """
        Calculate OBU position using specified method
        
        Args:
            rsu_positions: Dictionary mapping RSU ID to (x, y) coordinates
            rssi_measurements: Dictionary mapping RSU ID to RSSI value
            method: 'least_squares' or 'optimization'
            
        Returns:
            Tuple of (x, y, accuracy_estimate) or None if calculation fails
        """
        if method == 'least_squares':
            return self.calculate_position_least_squares(rsu_positions, rssi_measurements)
        elif method == 'optimization':
            return self.calculate_position_optimization(rsu_positions, rssi_measurements)
        else:
            raise ValueError(f"Unknown method: {method}")

class PositionFilter:
    """
    Simple Kalman-like filter for position smoothing
    """
    
    def __init__(self, process_noise: float = 0.1, measurement_noise: float = 1.0):
        self.process_noise = process_noise
        self.measurement_noise = measurement_noise
        self.last_position = None
        self.last_velocity = (0.0, 0.0)
        self.last_timestamp = None
    
    def update(self, new_position: Tuple[float, float], timestamp: float) -> Tuple[float, float]:
        """
        Update filter with new position measurement
        
        Args:
            new_position: New measured position (x, y)
            timestamp: Timestamp of measurement
            
        Returns:
            Filtered position (x, y)
        """
        if self.last_position is None:
            self.last_position = new_position
            self.last_timestamp = timestamp
            return new_position
        
        dt = timestamp - self.last_timestamp
        if dt <= 0:
            return self.last_position
        
        # Predict position based on last velocity
        predicted_x = self.last_position[0] + self.last_velocity[0] * dt
        predicted_y = self.last_position[1] + self.last_velocity[1] * dt
        
        # Simple weighted average (simplified Kalman filter)
        gain = self.process_noise / (self.process_noise + self.measurement_noise)
        
        filtered_x = predicted_x + gain * (new_position[0] - predicted_x)
        filtered_y = predicted_y + gain * (new_position[1] - predicted_y)
        
        # Update velocity estimate
        self.last_velocity = (
            (filtered_x - self.last_position[0]) / dt,
            (filtered_y - self.last_position[1]) / dt
        )
        
        self.last_position = (filtered_x, filtered_y)
        self.last_timestamp = timestamp
        
        return self.last_position