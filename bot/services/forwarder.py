import asyncio
import time
import logging
from typing import List, Dict, Optional
from pyrogram import Client
from pyrogram.errors import FloodWait, RPCError
from bot.core.db import update_job_progress, complete_job
from bot.services.logger import AdminLogger
from bot.services.rate_limiter import RateLimiter
from bot.utils.progress import calculate_speed, calculate_eta

logger = logging.getLogger(__name__)

class ForwardEngine:
    def __init__(self, client: Client, admin_logger: AdminLogger):
        self.client = client
        self.admin_logger = admin_logger
        self.paused_events: Dict[int, asyncio.Event] = {}
        self.running_jobs: Dict[int, asyncio.Task] = {}
    
    def should_forward_message(self, message, filter_type: str) -> bool:
        if filter_type == "all":
            return True
        elif filter_type == "media_only":
            return bool(message.photo or message.video or message.audio or 
                       message.document or message.animation)
        elif filter_type == "text_only":
            return bool(message.text)
        elif filter_type == "photos_only":
            return bool(message.photo)
        elif filter_type == "videos_only":
            return bool(message.video)
        elif filter_type == "docs_only":
            return bool(message.document or message.animation)
        return True
    
    async def forward_message_with_retry(self, dest_chat: str, message, 
                                         retry_enabled: bool, max_retries: int,
                                         rate_limiter: RateLimiter) -> tuple:
        retries = 0
        while True:
            try:
                await self.client.copy_message(
                    chat_id=dest_chat,
                    from_chat_id=message.chat.id,
                    message_id=message.id
                )
                return True, 0
            except FloodWait as e:
                logger.warning(f"FloodWait: {e.value}s")
                await rate_limiter.handle_flood_wait(e.value)
                retries += 1
                if not retry_enabled or retries >= max_retries:
                    return False, retries
                continue
            except RPCError as e:
                logger.error(f"RPCError forwarding to {dest_chat}: {e}")
                if not retry_enabled or retries >= max_retries:
                    return False, retries
                retries += 1
                await asyncio.sleep(2 ** retries)
                continue
            except Exception as e:
                logger.error(f"Unexpected error forwarding to {dest_chat}: {e}")
                return False, retries
    
    async def run_forwarding_job(self, job_id: int, user_id: int, 
                                  source_id: str, destinations: List[Dict],
                                  total: int, delay: float, filter_type: str,
                                  settings: Dict, admin_message_id: int,
                                  job_data: Dict):
        rate_limiter = RateLimiter(delay)
        start_time = time.time()
        forwarded_count = 0
        errors_total = 0
        retries_total = 0
        last_progress_update = 0
        
        self.paused_events[job_id] = asyncio.Event()
        self.paused_events[job_id].set()

        # DEBUG - print job info
        print(f"[JOB {job_id}] Starting...")
        print(f"[JOB {job_id}] Source: {source_id}")
        print(f"[JOB {job_id}] Destinations: {destinations}")
        print(f"[JOB {job_id}] Total: {total}, Delay: {delay}, Filter: {filter_type}")
        
        try:
            message_count = 0
            print(f"[JOB {job_id}] Fetching messages from {source_id}...")

            async for message in self.client.get_chat_history(source_id, limit=total):
                if not self.running_jobs.get(job_id):
                    print(f"[JOB {job_id}] Job stopped.")
                    break
                
                await self.paused_events[job_id].wait()
                
                if not self.should_forward_message(message, filter_type):
                    continue
                
                if message.media_group_id:
                    continue
                
                print(f"[JOB {job_id}] Forwarding msg {message.id} to {len(destinations)} destinations...")

                for dest in destinations:
                    print(f"[JOB {job_id}] → Sending to {dest['id']} ({dest['name']})")
                    success, retries = await self.forward_message_with_retry(
                        dest['id'], message, settings['retry_enabled'],
                        settings['max_retries'], rate_limiter
                    )
                    
                    if success:
                        print(f"[JOB {job_id}] ✅ Sent to {dest['id']}")
                    else:
                        print(f"[JOB {job_id}] ❌ Failed to send to {dest['id']}")
                        errors_total += 1
                    retries_total += retries
                    
                    await rate_limiter.wait_with_delay(rate_limiter.get_delay())
                
                forwarded_count += 1
                message_count += 1
                
                current_time = time.time()
                if message_count - last_progress_update >= 5:
                    last_progress_update = message_count
                    await update_job_progress(job_id, message_count, 
                                              errors_total, retries_total)
                    speed = calculate_speed(message_count, current_time - start_time)
                    eta = calculate_eta(start_time, message_count, total)
                    try:
                        await self.admin_logger.update_job_progress(
                            admin_message_id, job_data, message_count, total,
                            speed, eta, "🟢", "Running"
                        )
                    except Exception as e:
                        logger.warning(f"Admin log update failed: {e}")
                
                if message_count >= total:
                    break
            
            print(f"[JOB {job_id}] ✅ Completed! Forwarded: {forwarded_count}, Errors: {errors_total}")
            await complete_job(job_id, "completed")
            elapsed = time.time() - start_time
            speed = calculate_speed(forwarded_count, elapsed)
            try:
                await self.admin_logger.update_job_progress(
                    admin_message_id, job_data, forwarded_count, total,
                    speed, "0s", "✅", "Completed"
                )
            except Exception as e:
                logger.warning(f"Admin log final update failed: {e}")
            
        except asyncio.CancelledError:
            print(f"[JOB {job_id}] Cancelled.")
            await complete_job(job_id, "cancelled")
            raise
        except Exception as e:
            print(f"[JOB {job_id}] ❌ FATAL ERROR: {e}")
            logger.exception(f"Job {job_id} failed with exception")
            await complete_job(job_id, "failed")
        finally:
            if job_id in self.paused_events:
                del self.paused_events[job_id]
            if job_id in self.running_jobs:
                del self.running_jobs[job_id]
    
    async def pause_job(self, job_id: int):
        if job_id in self.paused_events:
            self.paused_events[job_id].clear()
            await update_job_progress(job_id, status="paused")
    
    async def resume_job(self, job_id: int):
        if job_id in self.paused_events:
            self.paused_events[job_id].set()
            await update_job_progress(job_id, status="running")
    
    async def cancel_job(self, job_id: int):
        if job_id in self.running_jobs:
            self.running_jobs[job_id].cancel()
            await complete_job(job_id, "cancelled")