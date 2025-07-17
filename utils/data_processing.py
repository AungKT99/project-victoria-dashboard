"""
Data processing utilities for Project Victoria Dashboard
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
import json

def format_rssi_for_display(rssi_value: float) -> str:
    """
    Format RSSI value for display with appropriate color coding
    
    Args:
        rssi_value: RSSI value in dBm
        
    Returns:
        Formatted string with signal quality indicator
    """
    if rssi_value >= -50:
        quality = "Excellent"
        bars = "█████████"
    elif rssi_value >= -60:
        quality = "Very Good"
        bars = "████████▒"
    elif rssi_value >= -70:
        quality = "Good"
        bars = "██████▒▒▒"
    elif rssi_value >= -80:
        quality = "Fair"
        bars = "████▒▒▒▒▒"
    elif rssi_value >= -90:
        quality = "Poor"
        bars = "██▒▒▒▒▒▒▒"
    else:
        quality = "Very Poor"
        bars = "▒▒▒▒▒▒▒▒▒"
    
    return f"{rssi_value:.1f} dBm {bars} ({quality})"

def calculate_data_rate(position_history: List[Dict]) -> float:
    """
    Calculate data update rate from position history
    
    Args:
        position_history: List of position data dictionaries
        
    Returns:
        Data rate in Hz
    """
    if len(position_history) < 2:
        return 0.0
    
    try:
        # Get timestamps from last 10 data points
        recent_data = position_history[-10:]
        timestamps = []
        
        for data in recent_data:
            if 'timestamp' in data:
                timestamp = datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))
                timestamps.append(timestamp)
        
        if len(timestamps) < 2:
            return 0.0
        
        # Calculate average time difference
        time_diffs = []
        for i in range(1, len(timestamps)):
            diff = (timestamps[i] - timestamps[i-1]).total_seconds()
            if diff > 0:
                time_diffs.append(diff)
        
        if time_diffs:
            avg_interval = sum(time_diffs) / len(time_diffs)
            return 1.0 / avg_interval if avg_interval > 0 else 0.0
        
    except Exception:
        pass
    
    return 0.0

def export_data_to_csv(position_history: List[Dict], 
                      rssi_data: Dict,
                      filename: Optional[str] = None) -> str:
    """
    Export position and RSSI data to CSV format
    
    Args:
        position_history: List of position data dictionaries
        rssi_data: Current RSSI data
        filename: Optional filename for export
        
    Returns:
        CSV data as string
    """
    if filename is None:
        filename = f"project_victoria_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    # Prepare data for CSV
    csv_data = []
    
    for entry in position_history:
        row = {
            'timestamp': entry.get('timestamp', ''),
            'x_position': entry.get('x', ''),
            'y_position': entry.get('y', ''),
            'accuracy': entry.get('accuracy', ''),
        }
        
        # Add RSSI data if available
        if 'rssi_data' in entry:
            for rsu_id, rsu_data in entry['rssi_data'].items():
                row[f'{rsu_id}_rssi'] = rsu_data.get('rssi', '')
                row[f'{rsu_id}_timestamp'] = rsu_data.get('timestamp', '')
        
        csv_data.append(row)
    
    # Convert to DataFrame and then to CSV
    df = pd.DataFrame(csv_data)
    csv_string = df.to_csv(index=False)
    
    return csv_string



def validate_position_data(position_data: Dict) -> List[str]:
    """
    Validate position data for completeness and reasonableness
    
    Args:
        position_data: Position data dictionary
        
    Returns:
        List of validation warnings/errors
    """
    warnings = []
    
    # Check required fields
    required_fields = ['x', 'y', 'timestamp']
    for field in required_fields:
        if field not in position_data:
            warnings.append(f"Missing required field: {field}")
    
    # Check data types and ranges
    if 'x' in position_data:
        try:
            x = float(position_data['x'])
            if x < -1000 or x > 1000:  # Reasonable range check
                warnings.append(f"X coordinate seems unreasonable: {x}")
        except (ValueError, TypeError):
            warnings.append("X coordinate is not a valid number")
    
    if 'y' in position_data:
        try:
            y = float(position_data['y'])
            if y < -1000 or y > 1000:  # Reasonable range check
                warnings.append(f"Y coordinate seems unreasonable: {y}")
        except (ValueError, TypeError):
            warnings.append("Y coordinate is not a valid number")
    
    if 'accuracy' in position_data:
        try:
            accuracy = float(position_data['accuracy'])
            if accuracy < 0:
                warnings.append("Accuracy cannot be negative")
            elif accuracy > 100:
                warnings.append(f"Accuracy seems very poor: ±{accuracy:.1f}m")
        except (ValueError, TypeError):
            warnings.append("Accuracy is not a valid number")
    
    # Check timestamp format
    if 'timestamp' in position_data:
        try:
            datetime.fromisoformat(position_data['timestamp'].replace('Z', '+00:00'))
        except ValueError:
            warnings.append("Invalid timestamp format")
    
    return warnings