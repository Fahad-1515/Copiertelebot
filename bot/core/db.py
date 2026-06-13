import aiosqlite
import json
from typing import Optional, List, Dict, Any

DB_PATH = "forward_bot.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                source_id TEXT,
                source_name TEXT,
                destinations_json TEXT,
                total INTEGER,
                forwarded INTEGER DEFAULT 0,
                errors INTEGER DEFAULT 0,
                retries INTEGER DEFAULT 0,
                status TEXT,
                delay_used REAL,
                filter_type TEXT,
                admin_log_message_id INTEGER,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                user_id INTEGER PRIMARY KEY,
                default_delay REAL DEFAULT 1.0,
                retry_enabled INTEGER DEFAULT 1,
                forward_mode TEXT DEFAULT 'copy',
                max_retries INTEGER DEFAULT 3,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        """)
        
        await db.commit()

async def add_user(user_id: int, username: str, first_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
            (user_id, username or "", first_name or "")
        )
        await db.commit()

async def create_job(user_id: int, source_id: str, source_name: str, 
                     destinations: List[Dict], total: int, delay: float, 
                     filter_type: str, admin_log_message_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO jobs (user_id, source_id, source_name, destinations_json, 
               total, delay_used, filter_type, admin_log_message_id, status) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, source_id, source_name, json.dumps(destinations), 
             total, delay, filter_type, admin_log_message_id, "running")
        )
        await db.commit()
        return cursor.lastrowid

async def update_job_progress(job_id: int, forwarded: int, errors: int = None, 
                              retries: int = None, status: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        updates = []
        params = []
        if forwarded is not None:
            updates.append("forwarded = ?")
            params.append(forwarded)
        if errors is not None:
            updates.append("errors = ?")
            params.append(errors)
        if retries is not None:
            updates.append("retries = ?")
            params.append(retries)
        if status is not None:
            updates.append("status = ?")
            params.append(status)
        
        if updates:
            params.append(job_id)
            await db.execute(
                f"UPDATE jobs SET {', '.join(updates)} WHERE id = ?",
                params
            )
            await db.commit()

async def complete_job(job_id: int, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE jobs SET status = ?, completed_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, job_id)
        )
        await db.commit()

async def get_user_jobs(user_id: int) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, source_name, total, forwarded, status, started_at, completed_at FROM jobs WHERE user_id = ? ORDER BY started_at DESC LIMIT 50",
            (user_id,)
        )
        rows = await cursor.fetchall()
        return [{"id": r[0], "source_name": r[1], "total": r[2], 
                 "forwarded": r[3], "status": r[4], "started_at": r[5], 
                 "completed_at": r[6]} for r in rows]

async def get_user_settings(user_id: int) -> Dict:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT default_delay, retry_enabled, forward_mode, max_retries FROM settings WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        if row:
            return {"default_delay": row[0], "retry_enabled": bool(row[1]), 
                    "forward_mode": row[2], "max_retries": row[3]}
        return {"default_delay": 1.0, "retry_enabled": True, 
                "forward_mode": "copy", "max_retries": 3}

async def update_user_settings(user_id: int, settings: Dict):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT OR REPLACE INTO settings 
               (user_id, default_delay, retry_enabled, forward_mode, max_retries) 
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, settings.get("default_delay", 1.0), 
             int(settings.get("retry_enabled", True)),
             settings.get("forward_mode", "copy"), 
             settings.get("max_retries", 3))
        )
        await db.commit()

async def get_user_stats(user_id: int) -> Dict:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """SELECT 
                SUM(forwarded) as total_forwarded,
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
                COUNT(CASE WHEN status = 'cancelled' THEN 1 END) as cancelled,
                COUNT(CASE WHEN status = 'paused' THEN 1 END) as paused,
                AVG(delay_used) as avg_delay
               FROM jobs WHERE user_id = ?""",
            (user_id,)
        )
        row = await cursor.fetchone()
        return {"total_forwarded": row[0] or 0, "completed": row[1] or 0,
                "cancelled": row[2] or 0, "paused": row[3] or 0, 
                "avg_delay": row[4] or 0}

async def get_job(job_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, user_id, source_id, source_name, destinations_json, total, forwarded, errors, retries, status, delay_used, filter_type, admin_log_message_id FROM jobs WHERE id = ?",
            (job_id,)
        )
        row = await cursor.fetchone()
        if row:
            return {"id": row[0], "user_id": row[1], "source_id": row[2], 
                    "source_name": row[3], "destinations": json.loads(row[4]), 
                    "total": row[5], "forwarded": row[6], "errors": row[7], 
                    "retries": row[8], "status": row[9], "delay_used": row[10], 
                    "filter_type": row[11], "admin_log_message_id": row[12]}
        return None

async def update_job_admin_message(job_id: int, message_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE jobs SET admin_log_message_id = ? WHERE id = ?",
            (message_id, job_id)
        )
        await db.commit()