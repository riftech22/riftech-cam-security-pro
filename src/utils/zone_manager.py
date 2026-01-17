"""
Security Zone Manager
Manages polygon-based security zones with breach detection
"""

import cv2
import numpy as np
import time
import math
from typing import List, Tuple, Dict, Optional

from ..core.logger import logger


class SecurityZone:
    """Security zone with breach detection"""
    
    _id_counter = 0
    
    def __init__(self, name: str = "Zone"):
        SecurityZone._id_counter += 1
        self.zone_id = SecurityZone._id_counter
        self.name = name
        self.points: List[Tuple[int, int]] = []
        self.is_complete = False
        self.is_active = True
        
        # Breach state
        self.breach_active = False
        self.breach_start_time = None
        self.breach_duration = 0
        
        # Animation state
        self.scan_position = 0.0
        self.scan_direction = 1
        self.last_update = time.time()
        self.pulse_phase = 0.0
    
    def add_point(self, x: int, y: int):
        """Add a point to the zone"""
        self.points.append((x, y))
        if len(self.points) >= 3:
            self.is_complete = True
    
    def contains_point(self, x: int, y: int) -> bool:
        """
        Check if point is inside zone using ray casting algorithm
        
        Args:
            x: X coordinate
            y: Y coordinate
            
        Returns:
            True if point is inside zone
        """
        if not self.is_complete or len(self.points) < 3:
            return False
        
        n = len(self.points)
        inside = False
        
        j = n - 1
        for i in range(n):
            xi, yi = self.points[i]
            xj, yj = self.points[j]
            
            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
                inside = not inside
            j = i
        
        return inside
    
    def update_breach(self, person_center: Tuple[int, int]) -> bool:
        """
        Update breach state based on person position
        
        Args:
            person_center: (x, y) center of detected person
            
        Returns:
            True if breach state changed
        """
        is_breached = self.contains_point(*person_center)
        
        if is_breached and not self.breach_active:
            # Breach started
            self.breach_active = True
            self.breach_start_time = time.time()
            logger.info(f"Zone {self.zone_id} breach detected!")
            return True
        elif not is_breached and self.breach_active:
            # Breach ended
            self.breach_active = False
            self.breach_duration = 0
            logger.info(f"Zone {self.zone_id} breach cleared")
            return True
        
        # Update duration if breach is active
        if self.breach_active and self.breach_start_time:
            self.breach_duration = int(time.time() - self.breach_start_time)
        
        return False
    
    def get_bounding_box(self) -> Optional[Tuple[int, int, int, int]]:
        """Get bounding box of zone"""
        if not self.points:
            return None
        
        x_coords = [p[0] for p in self.points]
        y_coords = [p[1] for p in self.points]
        
        return (min(x_coords), min(y_coords), max(x_coords), max(y_coords))
    
    def clear(self):
        """Clear zone points"""
        self.points.clear()
        self.is_complete = False
        self.breach_active = False
        self.breach_duration = 0


class ZoneManager:
    """Manages multiple security zones"""
    
    def __init__(self):
        self.zones: List[SecurityZone] = []
        self.active_zone_idx = -1
        self.is_armed = False
    
    def create_zone(self, name: str = "Zone") -> SecurityZone:
        """Create a new zone"""
        zone = SecurityZone(name)
        self.zones.append(zone)
        self.active_zone_idx = len(self.zones) - 1
        logger.info(f"Created zone {zone.zone_id}: {name}")
        return zone
    
    def get_active_zone(self) -> Optional[SecurityZone]:
        """Get currently active zone"""
        if 0 <= self.active_zone_idx < len(self.zones):
            return self.zones[self.active_zone_idx]
        return None
    
    def check_breaches(self, person_centers: List[Tuple[int, int]]) -> List[int]:
        """
        Check all zones for breaches
        
        Args:
            person_centers: List of person center points
            
        Returns:
            List of zone IDs that are breached
        """
        breached_zones = []
        
        for zone in self.zones:
            if not zone.is_complete:
                continue
            
            # Check if any person is in the zone
            for center in person_centers:
                zone_state_changed = zone.update_breach(center)
                
                if zone.breach_active and zone.zone_id not in breached_zones:
                    breached_zones.append(zone.zone_id)
                elif not zone.breach_active and zone_state_changed:
                    # Zone cleared, remove from list
                    if zone.zone_id in breached_zones:
                        breached_zones.remove(zone.zone_id)
        
        return breached_zones
    
    def get_zone_count(self) -> int:
        """Get number of complete zones"""
        return sum(1 for z in self.zones if z.is_complete)
    
    def delete_all_zones(self):
        """Delete all zones"""
        self.zones.clear()
        self.active_zone_idx = -1
        SecurityZone._id_counter = 0
        logger.info("All zones deleted")
    
    def get_all_zones(self) -> List[Dict]:
        """Get all zones as dictionaries"""
        zones_data = []
        
        for zone in self.zones:
            zones_data.append({
                'id': zone.zone_id,
                'name': zone.name,
                'points': zone.points,
                'is_complete': zone.is_complete,
                'is_active': zone.is_active,
                'breach_active': zone.breach_active,
                'breach_duration': zone.breach_duration
            })
        
        return zones_data
    
    def draw_zones(
        self,
        frame: np.ndarray,
        breached_ids: List[int] = None
    ) -> np.ndarray:
        """
        Draw all zones on frame
        
        Args:
            frame: Input frame
            breached_ids: List of breached zone IDs
            
        Returns:
            Frame with zones drawn
        """
        if breached_ids is None:
            breached_ids = []
        
        frame = frame.copy()
        
        for zone in self.zones:
            if not zone.is_complete or len(zone.points) < 3:
                # Draw incomplete zone
                for i, pt in enumerate(zone.points):
                    cv2.circle(frame, pt, 8, (0, 255, 255), 2)
                    if i > 0:
                        cv2.line(frame, zone.points[i-1], pt, (0, 255, 255), 2)
                continue
            
            # Determine color based on breach state
            is_breached = zone.zone_id in breached_ids
            
            if is_breached:
                color = (0, 0, 255)  # Red for breach
                fill_color = (0, 0, 100)
                text = "!! BREACH !!"
            else:
                color = (0, 255, 255)  # Cyan for normal
                fill_color = (0, 100, 100)
                text = "ZONE" if not self.is_armed else "ARMED"
            
            # Draw filled polygon
            pts = np.array(zone.points, dtype=np.int32)
            overlay = frame.copy()
            cv2.fillPoly(overlay, [pts], fill_color)
            frame = cv2.addWeighted(overlay, 0.3, frame, 0.7, 0)
            
            # Draw polygon border
            cv2.polylines(frame, [pts], True, color, 3)
            
            # Draw points
            for pt in zone.points:
                cv2.circle(frame, pt, 6, color, -1)
                cv2.circle(frame, pt, 8, (255, 255, 255), 2)
            
            # Draw zone name
            bbox = zone.get_bounding_box()
            if bbox:
                x1, y1, x2, y2 = bbox
                center_x = (x1 + x2) // 2
                center_y = (y1 + y2) // 2
                
                # Draw text background
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 0.7
                thickness = 2
                
                (tw, th), _ = cv2.getTextSize(text, font, font_scale, thickness)
                text_x = center_x - tw // 2
                text_y = y1 - 15
                
                cv2.rectangle(frame, (text_x - 5, text_y - th - 5), 
                           (text_x + tw + 5, text_y + 5), (0, 0, 0), -1)
                cv2.putText(frame, text, (text_x, text_y), font,
                           font_scale, color, thickness)
                
                # Draw zone ID
                id_text = f"#{zone.zone_id}"
                cv2.putText(frame, id_text, (x1, y2 + 20), font,
                           0.5, color, 1)
        
        return frame
