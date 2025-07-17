"""
Field configuration utilities for Project Victoria Dashboard
"""
import numpy as np
from typing import Dict, Tuple, List

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

def calculate_optimal_rsu_positions(field_width: float, 
                                  field_height: float, 
                                  num_rsus: int = 3) -> Dict[str, Tuple[float, float]]:
    """
    Calculate optimal RSU positions for maximum coverage
    
    Args:
        field_width: Field width in meters
        field_height: Field height in meters
        num_rsus: Number of RSUs to position
        
    Returns:
        Dictionary mapping RSU ID to optimal (x, y) coordinates
    """
    positions = {}
    
    if num_rsus == 3:
        # Triangle formation for best trilateration accuracy
        margin = min(field_width, field_height) * 0.1  # 10% margin from edges
        
        positions = {
            "RSU1": (margin, margin),
            "RSU2": (field_width - margin, margin),
            "RSU3": (field_width / 2, field_height - margin)
        }
    
    elif num_rsus == 4:
        # Rectangle formation
        margin = min(field_width, field_height) * 0.1
        
        positions = {
            "RSU1": (margin, margin),
            "RSU2": (field_width - margin, margin),
            "RSU3": (field_width - margin, field_height - margin),
            "RSU4": (margin, field_height - margin)
        }
    
    else:
        # Distribute RSUs around the perimeter
        margin = min(field_width, field_height) * 0.1
        perimeter_points = []
        
        # Calculate perimeter points
        if num_rsus >= 2:
            # Bottom edge
            for i in range(max(1, num_rsus // 4)):
                x = margin + (field_width - 2 * margin) * i / max(1, num_rsus // 4 - 1) if num_rsus // 4 > 1 else field_width / 2
                perimeter_points.append((x, margin))
            
            # Right edge
            for i in range(max(1, num_rsus // 4)):
                y = margin + (field_height - 2 * margin) * i / max(1, num_rsus // 4 - 1) if num_rsus // 4 > 1 else field_height / 2
                perimeter_points.append((field_width - margin, y))
            
            # Top edge
            for i in range(max(1, num_rsus // 4)):
                x = field_width - margin - (field_width - 2 * margin) * i / max(1, num_rsus // 4 - 1) if num_rsus // 4 > 1 else field_width / 2
                perimeter_points.append((x, field_height - margin))
            
            # Left edge
            for i in range(max(1, num_rsus - 3 * (num_rsus // 4))):
                y = field_height - margin - (field_height - 2 * margin) * i / max(1, num_rsus - 3 * (num_rsus // 4) - 1) if num_rsus - 3 * (num_rsus // 4) > 1 else field_height / 2
                perimeter_points.append((margin, y))
        
        # Assign positions
        for i, point in enumerate(perimeter_points[:num_rsus]):
            positions[f"RSU{i+1}"] = point
    
    return positions

def calculate_coverage_quality(rsu_positions: Dict[str, Tuple[float, float]],
                             field_width: float,
                             field_height: float,
                             grid_resolution: float = 1.0) -> float:
    """
    Calculate coverage quality score for given RSU positions
    
    Args:
        rsu_positions: Dictionary mapping RSU ID to (x, y) coordinates
        field_width: Field width in meters
        field_height: Field height in meters
        grid_resolution: Grid resolution for analysis in meters
        
    Returns:
        Coverage quality score (0-1, higher is better)
    """
    if len(rsu_positions) < 3:
        return 0.0
    
    # Create grid of test points
    x_points = np.arange(0, field_width + grid_resolution, grid_resolution)
    y_points = np.arange(0, field_height + grid_resolution, grid_resolution)
    
    total_points = 0
    well_covered_points = 0
    
    for x in x_points:
        for y in y_points:
            total_points += 1
            
            # Calculate distance to each RSU
            distances = []
            for rsu_pos in rsu_positions.values():
                dist = np.sqrt((x - rsu_pos[0])**2 + (y - rsu_pos[1])**2)
                distances.append(dist)
            
            # Check if point has good coverage (within range of at least 3 RSUs)
            max_range = 50.0  # meters, typical V2X range
            rsus_in_range = sum(1 for d in distances if d <= max_range)
            
            if rsus_in_range >= 3:
                # Additional quality check: geometric dilution of precision
                if len(rsu_positions) >= 3:
                    gdop = calculate_gdop_at_point((x, y), rsu_positions)
                    if gdop < 2.0:  # Good GDOP threshold
                        well_covered_points += 1
    
    return well_covered_points / total_points if total_points > 0 else 0.0

def calculate_gdop_at_point(point: Tuple[float, float], 
                           rsu_positions: Dict[str, Tuple[float, float]]) -> float:
    """
    Calculate Geometric Dilution of Precision (GDOP) at a given point
    
    Args:
        point: Test point (x, y)
        rsu_positions: Dictionary mapping RSU ID to (x, y) coordinates
        
    Returns:
        GDOP value (lower is better)
    """
    if len(rsu_positions) < 3:
        return float('inf')
    
    px, py = point
    
    # Build geometry matrix
    H = []
    for rsu_pos in rsu_positions.values():
        rx, ry = rsu_pos
        distance = np.sqrt((px - rx)**2 + (py - ry)**2)
        
        if distance > 0:
            # Unit vector from RSU to point
            ux = (px - rx) / distance
            uy = (py - ry) / distance
            H.append([ux, uy])
    
    H = np.array(H)
    
    try:
        # Calculate GDOP
        HTH = np.dot(H.T, H)
        if np.linalg.det(HTH) > 1e-10:
            Q = np.linalg.inv(HTH)
            gdop = np.sqrt(np.trace(Q))
            return gdop
        else:
            return float('inf')
    except np.linalg.LinAlgError:
        return float('inf')

def suggest_rsu_improvements(current_positions: Dict[str, Tuple[float, float]],
                           field_width: float,
                           field_height: float) -> List[str]:
    """
    Suggest improvements to current RSU positioning
    
    Args:
        current_positions: Current RSU positions
        field_width: Field width in meters
        field_height: Field height in meters
        
    Returns:
        List of improvement suggestions
    """
    suggestions = []
    
    if len(current_positions) < 3:
        suggestions.append("Add more RSUs - at least 3 are needed for trilateration")
        return suggestions
    
    # Check coverage quality
    quality = calculate_coverage_quality(current_positions, field_width, field_height)
    if quality < 0.7:
        suggestions.append(f"Coverage quality is low ({quality:.1%}). Consider repositioning RSUs.")
    
    # Check if RSUs are too close together
    min_distance = float('inf')
    positions = list(current_positions.values())
    for i, pos1 in enumerate(positions):
        for pos2 in positions[i+1:]:
            dist = np.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)
            min_distance = min(min_distance, dist)
    
    min_recommended = min(field_width, field_height) * 0.3
    if min_distance < min_recommended:
        suggestions.append(f"RSUs are too close together (min: {min_distance:.1f}m). Spread them out more.")
    
    # Check if RSUs are near field edges
    edge_margin = min(field_width, field_height) * 0.05
    for rsu_id, (x, y) in current_positions.items():
        if (x < edge_margin or x > field_width - edge_margin or 
            y < edge_margin or y > field_height - edge_margin):
            suggestions.append(f"{rsu_id} is very close to field edge. Consider moving inward.")
    
    # Check geometric configuration
    if len(current_positions) >= 3:
        center_x = sum(pos[0] for pos in positions) / len(positions)
        center_y = sum(pos[1] for pos in positions) / len(positions)
        center_gdop = calculate_gdop_at_point((center_x, center_y), current_positions)
        
        if center_gdop > 2.0:
            suggestions.append("Poor geometric configuration detected. Try triangular or rectangular formation.")
    
    if not suggestions:
        suggestions.append("RSU positioning looks good!")
    
    return suggestions