"""
Field configuration utilities for Project Victoria Dashboard
"""
from typing import Dict, Tuple

def validate_rsu_positions(positions: Dict[str, Tuple[float, float]], 
                          field_width: float, 
                          field_height: float) -> Dict[str, str]:
    """
    Validate RSU positions within field boundaries
    
    Args:
        positions: Dictionary mapping RSU ID to (x, y) coordinates
        field_width: Field width in meters
        field_height: Field height in meters
        
    Returns:
        Dictionary mapping RSU ID to error message (empty if valid)
    """
    errors = {}
    
    for rsu_id, (x, y) in positions.items():
        rsu_errors = []
        
        if x < 0 or x > field_width:
            rsu_errors.append(f"X coordinate ({x:.1f}m) outside field bounds (0-{field_width}m)")
        
        if y < 0 or y > field_height:
            rsu_errors.append(f"Y coordinate ({y:.1f}m) outside field bounds (0-{field_height}m)")
        
        if rsu_errors:
            errors[rsu_id] = "; ".join(rsu_errors)
    
    return errors