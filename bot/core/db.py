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
                skipped INTEGER DEFAULT 0,
                status TEXT,
                delay_used REAL,
                filter_type TEXT,
                admin_log_message_id INTEGER,
                start_msg_id INTEGER DEFAULT 1,
                last_msg_id INTEGER DEFAULT 0,
                status_chat_id INTEGER,
                status_message_id INTEGER,
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
                strip_links INTEGER DEFAULT 1,
                strip_mentions INTEGER DEFAULT 0,
                media_only INTEGER DEFAULT 0,
                text_only INTEGER DEFAULT 0,
                auto_resume INTEGER DEFAULT 1,
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
                     filter_type: str, admin_log_message_id: int,
                     start_msg_id: int = 1) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO jobs (user_id, source_id, source_name, destinations_json, 
               total, delay_used, filter_type, admin_log_message_id, start_msg_id, status) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, source_id, source_name, json.dumps(destinations), 
             total, delay, filter_type, admin_log_message_id, start_msg_id, "running")
        )
        await db.commit()
        return cursor.lastrowid

async def update_job_progress(job_id: int, forwarded: int = None, 
                              errors: int = None, retries: int = None,
                              skipped: int = None, last_msg_id: int = None,
                              status: str = None, status_chat_id: int = None,
                              status_message_id: int = None):
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
        if skipped is not None:
            updates.append("skipped = ?")
            params.append(skipped)
        if last_msg_id is not None:
            updates.append("last_msg_id = ?")
            params.append(last_msg_id)
        if status is not None:
            updates.append("status = ?")
            params.append(status)
        if status_chat_id is not None:
            updates.append("status_chat_id = ?")
            params.append(status_chat_id)
        if status_message_id is not None:
            updates.append("status_message_id = ?")
            params.append(status_message_id)
        
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
            """SELECT id, source_name, total, forwarded, errors, skipped, status, 
               started_at, completed_at, start_msg_id, last_msg_id 
               FROM jobs WHERE user_id = ? ORDER BY started_at DESC LIMIT 50""",
            (user_id,)
        )
        rows = await cursor.fetchall()
        return [{"id": r[0], "source_name": r[1], "total": r[2], 
                 "forwarded": r[3], "errors": r[4], "skipped": r[5],
                 "status": r[6], "started_at": r[7], "completed_at": r[8],
                 "start_msg_id": r[9], "last_msg_id": r[10]} for r in rows]

async def get_user_settings(user_id: int) -> Dict:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """SELECT default_delay, retry_enabled, forward_mode, max_retries,
               strip_links, strip_mentions, media_only, text_only, auto_resume
               FROM settings WHERE user_id = ?""",
            (user_id,)
        )
        row = await cursor.fetchone()
        if row:
            return {
                "default_delay": row[0],
                "retry_enabled": bool(row[1]),
                "forward_mode": row[2],
                "max_retries": row[3],
                "strip_links": bool(row[4]),
                "strip_mentions": bool(row[5]),
                "media_only": bool(row[6]),
                "text_only": bool(row[7]),
                "auto_resume": bool(row[8])
            }
        return {
            "default_delay": 1.0,
            "retry_enabled": True,
            "forward_mode": "copy",
            "max_retries": 3,
            "strip_links": True,
            "strip_mentions": False,
            "media_only": False,
            "text_only": False,
            "auto_resume": True
        }

async def update_user_settings(user_id: int, settings: Dict):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT OR REPLACE INTO settings 
               (user_id, default_delay, retry_enabled, forward_mode, max_retries,
                strip_links, strip_mentions, media_only, text_only, auto_resume) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id,
             settings.get("default_delay", 1.0),
             int(settings.get("retry_enabled", True)),
             settings.get("forward_mode", "copy"),
             settings.get("max_retries", 3),
             int(settings.get("strip_links", True)),
             int(settings.get("strip_mentions", False)),
             int(settings.get("media_only", False)),
             int(settings.get("text_only", False)),
             int(settings.get("auto_resume", True)))
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
            """SELECT id, user_id, source_id, source_name, destinations_json, 
               total, forwarded, errors, retries, skipped, status, delay_used, 
               filter_type, admin_log_message_id, start_msg_id, last_msg_id,
               status_chat_id, status_message_id
               FROM jobs WHERE id = ?""",
            (job_id,)
        )
        row = await cursor.fetchone()
        if row:
            return {
                "id": row[0], "user_id": row[1], "source_id": row[2],
                "source_name": row[3], "destinations": json.loads(row[4]),
                "total": row[5], "forwarded": row[6], "errors": row[7],
                "retries": row[8], "skipped": row[9], "status": row[10],
                "delay_used": row[11], "filter_type": row[12],
                "admin_log_message_id": row[13], "start_msg_id": row[14],
                "last_msg_id": row[15], "status_chat_id": row[16],
                "status_message_id": row[17]
            }
        return None

async def delete_job(job_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM jobs WHERE id = ? AND user_id = ?",
            (job_id, user_id)
        )
        await db.commit()

async def get_history(user_id: int, limit: int = 10) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """SELECT id, source_name, total, forwarded, errors, status,
               started_at, completed_at
               FROM jobs WHERE user_id = ? AND status IN ('completed', 'cancelled', 'failed')
               ORDER BY started_at DESC LIMIT ?""",
            (user_id, limit)
        )
        rows = await cursor.fetchall()
        return [{"id": r[0], "source_name": r[1], "total": r[2],
                 "forwarded": r[3], "errors": r[4], "status": r[5],
                 "started_at": r[6], "completed_at": r[7]} for r in rows]