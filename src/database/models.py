"""
Database Models and Queries
SQLite database with async support using aiosqlite
"""

import aiosqlite
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path
from contextlib import asynccontextmanager

from ..core.config import config
from ..core.logger import logger


class DatabaseManager:
    """Database manager with async operations"""
    
    def __init__(self):
        self.db_path = Path(config.paths.base_dir) / config.database.path
        self._lock = asyncio.Lock()
        self._initialized = False
    
    async def initialize(self):
        """Initialize database tables"""
        if self._initialized:
            return
        
        async with aiosqlite.connect(self.db_path) as db:
            await self._create_tables(db)
            await self._create_indexes(db)
            await db.commit()
        
        self._initialized = True
        logger.info(f"Database initialized at {self.db_path}")
    
    async def _create_tables(self, db: aiosqlite.Connection):
        """Create all database tables"""
        
        # Events table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                event_type TEXT NOT NULL,
                description TEXT,
                image_path TEXT,
                person_count INTEGER DEFAULT 0,
                zone_id INTEGER,
                confidence REAL
            )
        """)
        
        # Daily stats table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS daily_stats (
                date DATE PRIMARY KEY,
                alerts INTEGER DEFAULT 0,
                breaches INTEGER DEFAULT 0,
                persons_detected INTEGER DEFAULT 0,
                recording_minutes INTEGER DEFAULT 0
            )
        """)
        
        # Faces table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS faces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                image_path TEXT,
                added_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_seen DATETIME,
                seen_count INTEGER DEFAULT 0
            )
        """)
        
        # Zones table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS zones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                points TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1
            )
        """)
        
        # System settings table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
    
    async def _create_indexes(self, db: aiosqlite.Connection):
        """Create database indexes for performance"""
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type)",
            "CREATE INDEX IF NOT EXISTS idx_events_zone ON events(zone_id)",
            "CREATE INDEX IF NOT EXISTS idx_faces_name ON faces(name)",
            "CREATE INDEX IF NOT EXISTS idx_faces_last_seen ON faces(last_seen)"
        ]
        
        for index_sql in indexes:
            await db.execute(index_sql)
    
    async def log_event(self, event_type: str, description: str = "",
                      image_path: Optional[str] = None, person_count: int = 0,
                      zone_id: Optional[int] = None, confidence: Optional[float] = None):
        """Log an event"""
        async with self._get_connection() as db:
            await db.execute("""
                INSERT INTO events (event_type, description, image_path, person_count, zone_id, confidence)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (event_type, description, image_path, person_count, zone_id, confidence))
            await db.commit()
        
        logger.debug(f"Logged event: {event_type} - {description}")
    
    async def get_recent_events(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent events"""
        async with self._get_connection() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM events
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def get_events_by_type(self, event_type: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get events by type"""
        async with self._get_connection() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM events
                WHERE event_type = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (event_type, limit))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def get_events_in_range(self, start: datetime, end: datetime) -> List[Dict[str, Any]]:
        """Get events in date range"""
        async with self._get_connection() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM events
                WHERE timestamp BETWEEN ? AND ?
                ORDER BY timestamp DESC
            """, (start.isoformat(), end.isoformat()))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def update_daily_stats(self, alerts: int = 0, breaches: int = 0,
                               persons: int = 0, recording_mins: int = 0):
        """Update daily statistics"""
        today = datetime.now().date().isoformat()
        
        async with self._get_connection() as db:
            await db.execute("""
                INSERT INTO daily_stats (date, alerts, breaches, persons_detected, recording_minutes)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(date) DO UPDATE SET
                    alerts = alerts + excluded.alerts,
                    breaches = breaches + excluded.breaches,
                    persons_detected = persons_detected + excluded.persons_detected,
                    recording_minutes = recording_minutes + excluded.recording_minutes
            """, (today, alerts, breaches, persons, recording_mins))
            await db.commit()
    
    async def get_daily_stats(self, date: Optional[str] = None) -> Dict[str, int]:
        """Get daily statistics"""
        if date is None:
            date = datetime.now().date().isoformat()
        
        async with self._get_connection() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM daily_stats WHERE date = ?
            """, (date,))
            row = await cursor.fetchone()
            
            if row:
                return dict(row)
            return {'date': date, 'alerts': 0, 'breaches': 0, 'persons_detected': 0, 'recording_minutes': 0}
    
    async def get_weekly_stats(self) -> List[Dict[str, Any]]:
        """Get stats for the last 7 days"""
        async with self._get_connection() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM daily_stats
                WHERE date >= date('now', '-7 days')
                ORDER BY date DESC
            """)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def add_face(self, name: str, image_path: Optional[str] = None):
        """Add a new trusted face"""
        async with self._get_connection() as db:
            await db.execute("""
                INSERT OR IGNORE INTO faces (name, image_path)
                VALUES (?, ?)
            """, (name, image_path))
            await db.commit()
        logger.info(f"Added trusted face: {name}")
    
    async def update_face_seen(self, name: str):
        """Update last seen time for a face"""
        async with self._get_connection() as db:
            await db.execute("""
                UPDATE faces
                SET last_seen = CURRENT_TIMESTAMP, seen_count = seen_count + 1
                WHERE name = ?
            """, (name,))
            await db.commit()
    
    async def get_faces(self) -> List[Dict[str, Any]]:
        """Get all trusted faces"""
        async with self._get_connection() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM faces ORDER BY name
            """)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def get_face(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a specific face by name"""
        async with self._get_connection() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM faces WHERE name = ?
            """, (name,))
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def delete_face(self, name: str):
        """Delete a trusted face"""
        async with self._get_connection() as db:
            await db.execute("DELETE FROM faces WHERE name = ?", (name,))
            await db.commit()
        logger.info(f"Deleted trusted face: {name}")
    
    async def save_zone(self, name: str, points: List[tuple]) -> int:
        """Save a security zone"""
        import json
        points_json = json.dumps(points)
        
        async with self._get_connection() as db:
            cursor = await db.execute("""
                INSERT INTO zones (name, points)
                VALUES (?, ?)
            """, (name, points_json))
            await db.commit()
            return cursor.lastrowid
    
    async def get_zones(self) -> List[Dict[str, Any]]:
        """Get all zones"""
        import json
        
        async with self._get_connection() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM zones WHERE is_active = 1 ORDER BY id
            """)
            rows = await cursor.fetchall()
            
            zones = []
            for row in rows:
                zone = dict(row)
                zone['points'] = json.loads(zone['points'])
                zones.append(zone)
            
            return zones
    
    async def clear_zones(self):
        """Clear all zones"""
        async with self._get_connection() as db:
            await db.execute("UPDATE zones SET is_active = 0")
            await db.commit()
        logger.info("All zones cleared")
    
    async def set_setting(self, key: str, value: str):
        """Set a system setting"""
        async with self._get_connection() as db:
            await db.execute("""
                INSERT INTO settings (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = CURRENT_TIMESTAMP
            """, (key, value))
            await db.commit()
    
    async def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get a system setting"""
        async with self._get_connection() as db:
            cursor = await db.execute("""
                SELECT value FROM settings WHERE key = ?
            """, (key,))
            row = await cursor.fetchone()
            return row[0] if row else default
    
    async def cleanup_old_events(self, days: int = 30):
        """Delete events older than specified days"""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        async with self._get_connection() as db:
            cursor = await db.execute("""
                DELETE FROM events WHERE timestamp < ?
            """, (cutoff,))
            deleted = cursor.rowcount
            await db.commit()
            
            if deleted > 0:
                logger.info(f"Cleaned up {deleted} old events")
    
    async def get_event_count(self, event_type: Optional[str] = None) -> int:
        """Get total event count"""
        async with self._get_connection() as db:
            if event_type:
                cursor = await db.execute(
                    "SELECT COUNT(*) FROM events WHERE event_type = ?",
                    (event_type,)
                )
            else:
                cursor = await db.execute("SELECT COUNT(*) FROM events")
            
            row = await cursor.fetchone()
            return row[0] if row else 0
    
    @asynccontextmanager
    async def _get_connection(self):
        """Get database connection with lock"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                yield db


# Global database instance
db = DatabaseManager()
