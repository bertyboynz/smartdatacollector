import aiosqlite
import json
import os
from typing import Dict, List, Optional
from datetime import datetime

DATABASE_PATH = "/app/data/smartdata.db"

class Database:
    def __init__(self):
        self.db_path = DATABASE_PATH

    async def init_db(self):
        """Initialize database tables."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS drives (
                    serial TEXT PRIMARY KEY,
                    path TEXT NOT NULL,
                    model TEXT,
                    size TEXT,
                    excluded INTEGER DEFAULT 0,
                    last_seen TIMESTAMP
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS smart_readings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    serial TEXT NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    data TEXT NOT NULL,
                    FOREIGN KEY (serial) REFERENCES drives(serial)
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)

            await db.commit()

    async def upsert_drive(self, drive: Dict):
        """Insert or update drive information."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO drives (serial, path, model, size, last_seen)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(serial) DO UPDATE SET
                    path = excluded.path,
                    model = excluded.model,
                    size = excluded.size,
                    last_seen = excluded.last_seen
            """, (
                drive["serial"],
                drive["path"],
                drive.get("model"),
                drive.get("size"),
                datetime.utcnow().isoformat()
            ))
            await db.commit()

    async def store_reading(self, serial: str, data: Dict):
        """Store a SMART reading."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO smart_readings (serial, timestamp, data)
                VALUES (?, ?, ?)
            """, (
                serial,
                data["timestamp"],
                json.dumps(data)
            ))
            await db.commit()

    async def get_readings(self, serial: str, limit: int = 100) -> List[Dict]:
        """Get SMART readings for a drive."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT timestamp, data
                FROM smart_readings
                WHERE serial = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (serial, limit))

            rows = await cursor.fetchall()
            return [
                {"timestamp": row["timestamp"], "data": json.loads(row["data"])}
                for row in rows
            ]

    async def get_all_drives(self) -> List[Dict]:
        """Get all drives from database."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM drives")
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def set_excluded(self, serial: str, excluded: bool):
        """Set drive exclusion status."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE drives SET excluded = ? WHERE serial = ?
            """, (1 if excluded else 0, serial))
            await db.commit()

    async def get_config(self, key: str) -> Optional[str]:
        """Get configuration value."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT value FROM config WHERE key = ?",
                (key,)
            )
            row = await cursor.fetchone()
            return row[0] if row else None

    async def set_config(self, key: str, value: str):
        """Set configuration value."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO config (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """, (key, value))
            await db.commit()

    async def get_all_config(self) -> Dict[str, str]:
        """Get all configuration."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT key, value FROM config")
            rows = await cursor.fetchall()
            return {row[0]: row[1] for row in rows}

db = Database()