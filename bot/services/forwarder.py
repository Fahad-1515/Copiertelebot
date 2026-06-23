import asyncio
import time
import logging
import json
import os
import re
from typing import List, Dict, Optional, Tuple
from pyrogram import Client
from pyrogram.errors import FloodWait, RPCError, ChatWriteForbidden, MessageNotModified
from pyrogram.types import InputMediaPhoto, InputMediaVideo, InputMediaDocument, InputMediaAudio, InlineKeyboardMarkup, InlineKeyboardButton
from bot.core.db import update_job_progress, complete_job
from bot.services.logger import AdminLogger
from bot.services.rate_limiter import RateLimiter
from bot.utils.progress import calculate_speed, calculate_eta, format_time

logger = logging.getLogger(__name__)

class ForwardEngine:
    def __init__(self, client: Client, incomplete_jobs: Dict[int, Dict] = None):
        self.client = client
        self.paused_events: Dict[int, asyncio.Event] = {}
        self.running_jobs: Dict[int, asyncio.Task] = {}
        self.status_messages: Dict[int, Tuple[int, int]] = {}
        self.incomplete_jobs = incomplete_jobs or {}
        self.progress_dir = "progress"
        os.makedirs(self.progress_dir, exist_ok=True)
        
        for job_id, data in self.incomplete_jobs.items():
            self.paused_events[job_id] = asyncio.Event()
            self.paused_events[job_id].set()
            logger.info(f"Loaded incomplete job {job_id} with {data.get('forwarded', 0)} messages")
    
    def save_progress(self, job_id: int, data: Dict):
        path = os.path.join(self.progress_dir, f"{job_id}.json")
        with open(path, "w") as f:
            json.dump(data, f)
    
    def delete_progress(self, job_id: int):
        path = os.path.join(self.progress_dir, f"{job_id}.json")
        if os.path.exists(path):
            os.remove(path)
    
    def should_forward_message(self, message, filter_type: str, settings: Dict) -> bool:
        if filter_type == "all":
            if settings.get('media_only', False):
                return bool(message.photo or message.video or message.audio or 
                           message.document or message.animation)
            if settings.get('text_only', False):
                return bool(message.text)
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
    
    def clean_text(self, text: str, settings: Dict) -> str:
        if not text:
            return text
        if settings.get('strip_links', True):
            text = re.sub(r'https?://\S+', '', text)
        if settings.get('strip_mentions', False):
            text = re.sub(r'@\S+', '', text)
        return text.strip()
    
    async def send_single_message(self, dest_chat: str, message, settings: Dict,
                                   rate_limiter: RateLimiter, retry_enabled: bool,
                                   max_retries: int) -> Tuple[bool, int]:
        retries = 0
        while True:
            try:
                if message.text and not message.photo and not message.video and not message.document:
                    text = self.clean_text(message.text, settings)
                    if text:
                        await self.client.send_message(
                            chat_id=dest_chat,
                            text=text,
                            entities=message.entities
                        )
                    return True, 0
                
                elif message.photo:
                    caption = self.clean_text(message.caption or "", settings)
                    await self.client.send_photo(
                        chat_id=dest_chat,
                        photo=message.photo.file_id,
                        caption=caption
                    )
                    return True, 0
                
                elif message.video:
                    caption = self.clean_text(message.caption or "", settings)
                    await self.client.send_video(
                        chat_id=dest_chat,
                        video=message.video.file_id,
                        caption=caption,
                        duration=message.video.duration,
                        width=message.video.width,
                        height=message.video.height
                    )
                    return True, 0
                
                elif message.document:
                    caption = self.clean_text(message.caption or "", settings)
                    await self.client.send_document(
                        chat_id=dest_chat,
                        document=message.document.file_id,
                        caption=caption
                    )
                    return True, 0
                
                elif message.audio:
                    caption = self.clean_text(message.caption or "", settings)
                    await self.client.send_audio(
                        chat_id=dest_chat,
                        audio=message.audio.file_id,
                        caption=caption,
                        duration=message.audio.duration,
                        performer=message.audio.performer,
                        title=message.audio.title
                    )
                    return True, 0
                
                elif message.voice:
                    caption = self.clean_text(message.caption or "", settings)
                    await self.client.send_voice(
                        chat_id=dest_chat,
                        voice=message.voice.file_id,
                        caption=caption,
                        duration=message.voice.duration
                    )
                    return True, 0
                
                elif message.sticker:
                    await self.client.send_sticker(
                        chat_id=dest_chat,
                        sticker=message.sticker.file_id
                    )
                    return True, 0
                
                elif message.animation:
                    caption = self.clean_text(message.caption or "", settings)
                    await self.client.send_animation(
                        chat_id=dest_chat,
                        animation=message.animation.file_id,
                        caption=caption,
                        duration=message.animation.duration,
                        width=message.animation.width,
                        height=message.animation.height
                    )
                    return True, 0
                
                elif message.video_note:
                    await self.client.send_video_note(
                        chat_id=dest_chat,
                        video_note=message.video_note.file_id,
                        duration=message.video_note.duration,
                        length=message.video_note.length
                    )
                    return True, 0
                
                elif message.poll:
                    await self.client.send_poll(
                        chat_id=dest_chat,
                        question=message.poll.question,
                        options=[opt.text for opt in message.poll.options]
                    )
                    return True, 0
                
                elif message.contact:
                    await self.client.send_contact(
                        chat_id=dest_chat,
                        phone_number=message.contact.phone_number,
                        first_name=message.contact.first_name,
                        last_name=message.contact.last_name
                    )
                    return True, 0
                
                elif message.location:
                    await self.client.send_location(
                        chat_id=dest_chat,
                        latitude=message.location.latitude,
                        longitude=message.location.longitude
                    )
                    return True, 0
                
                elif message.venue:
                    await self.client.send_venue(
                        chat_id=dest_chat,
                        latitude=message.venue.location.latitude,
                        longitude=message.venue.location.longitude,
                        title=message.venue.title,
                        address=message.venue.address
                    )
                    return True, 0
                
                else:
                    return True, 0
                
            except FloodWait as e:
                logger.warning(f"FloodWait: {e.value}s for {dest_chat}")
                await rate_limiter.handle_flood_wait(e.value)
                retries += 1
                if not retry_enabled or retries >= max_retries:
                    return False, retries
                continue
            except ChatWriteForbidden:
                logger.error(f"Cannot write to {dest_chat} - bot is not admin")
                return False, retries
            except MessageNotModified:
                return True, 0
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
    
    async def send_album(self, dest_chat: str, messages: List, settings: Dict,
                         rate_limiter: RateLimiter, retry_enabled: bool,
                         max_retries: int) -> Tuple[bool, int]:
        retries = 0
        while True:
            try:
                media_group = []
                for msg in messages:
                    if msg.photo:
                        media_group.append(InputMediaPhoto(
                            media=msg.photo.file_id,
                            caption=self.clean_text(msg.caption or "", settings) if len(media_group) == 0 else ""
                        ))
                    elif msg.video:
                        media_group.append(InputMediaVideo(
                            media=msg.video.file_id,
                            caption=self.clean_text(msg.caption or "", settings) if len(media_group) == 0 else "",
                            duration=msg.video.duration,
                            width=msg.video.width,
                            height=msg.video.height
                        ))
                    elif msg.document:
                        media_group.append(InputMediaDocument(
                            media=msg.document.file_id,
                            caption=self.clean_text(msg.caption or "", settings) if len(media_group) == 0 else ""
                        ))
                    elif msg.audio:
                        media_group.append(InputMediaAudio(
                            media=msg.audio.file_id,
                            caption=self.clean_text(msg.caption or "", settings) if len(media_group) == 0 else "",
                            duration=msg.audio.duration,
                            performer=msg.audio.performer,
                            title=msg.audio.title
                        ))
                
                if media_group:
                    await self.client.send_media_group(
                        chat_id=dest_chat,
                        media=media_group
                    )
                return True, 0
                
            except FloodWait as e:
                logger.warning(f"FloodWait: {e.value}s for album to {dest_chat}")
                await rate_limiter.handle_flood_wait(e.value)
                retries += 1
                if not retry_enabled or retries >= max_retries:
                    return False, retries
                continue
            except ChatWriteForbidden:
                logger.error(f"Cannot write to {dest_chat} - bot is not admin")
                return False, retries
            except RPCError as e:
                logger.error(f"RPCError sending album to {dest_chat}: {e}")
                if not retry_enabled or retries >= max_retries:
                    return False, retries
                retries += 1
                await asyncio.sleep(2 ** retries)
                continue
            except Exception as e:
                logger.error(f"Unexpected error sending album to {dest_chat}: {e}")
                return False, retries
    
    async def update_user_status(self, job_id: int, job_data: Dict, forwarded: int,
                                 skipped: int, errors: int, last_msg_id: int,
                                 total: int, delay: float, elapsed: float,
                                 status_text: str, status_emoji: str = "🔄",
                                 show_buttons: bool = True):
        chat_id, message_id = self.status_messages.get(job_id, (None, None))
        if not chat_id or not message_id:
            return
        
        speed = calculate_speed(forwarded, elapsed) if elapsed > 0 else 0
        speed_min = speed * 60
        
        if total > 0 and total < 999999:
            percent = min(forwarded / total, 1.0)
            filled = int(12 * percent)
            bar = "█" * filled + "░" * (12 - filled)
            progress_text = f"📊 Progress: {bar} {int(percent * 100)}%"
        else:
            progress_text = f"📊 Forwarded: {forwarded:,} messages"
        
        text = f"""🔄 COPYING IN PROGRESS
━━━━━━━━━━━━━━━━━━━━
📤 Source:      {job_data.get('source_name', 'Unknown')}
📥 Destination: {len(job_data.get('destinations', []))} chats
━━━━━━━━━━━━━━━━━━━━
✅ Forwarded:   {forwarded:,} messages
⏭ Skipped:     {skipped:,}
❌ Errors:      {errors:,}
📍 Current:     msg #{last_msg_id}
⏱ Elapsed:     {format_time(elapsed)}
⚡ Speed:       ~{speed_min:.1f} msg/min
━━━━━━━━━━━━━━━━━━━━
{progress_text}"""
        
        keyboard = None
        if show_buttons:
            if status_text == "PAUSED":
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("▶️ Resume", callback_data=f"resume_job_{job_id}"),
                     InlineKeyboardButton("🛑 Stop", callback_data=f"stop_job_{job_id}")]
                ])
            else:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("⏸️ Pause", callback_data=f"pause_job_{job_id}"),
                     InlineKeyboardButton("🛑 Stop", callback_data=f"stop_job_{job_id}")]
                ])
        
        try:
            if status_text == "DONE":
                text = f"""✅ COMPLETE — {forwarded} messages copied in {format_time(elapsed)}
━━━━━━━━━━━━━━━━━━━━
📤 Source:      {job_data.get('source_name', 'Unknown')}
📥 Destination: {len(job_data.get('destinations', []))} chats
✅ Forwarded:   {forwarded:,}
⏭ Skipped:     {skipped:,}
❌ Errors:      {errors:,}
⏱ Total time:  {format_time(elapsed)}"""
                await self.client.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=text
                )
            else:
                await self.client.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=text,
                    reply_markup=keyboard
                )
        except MessageNotModified:
            pass
        except Exception as e:
            logger.warning(f"Failed to update status message: {e}")
    
    async def run_forwarding_job(self, job_id: int, user_id: int,
                                  source_id: str, destinations: List[Dict],
                                  total: int, delay: float, filter_type: str,
                                  settings: Dict, admin_message_id: int,
                                  job_data: Dict, start_msg_id: int = 1):
        rate_limiter = RateLimiter(delay)
        start_time = time.time()
        forwarded_count = 0
        errors_total = 0
        retries_total = 0
        skipped_count = 0
        last_msg_id = start_msg_id - 1
        last_progress_update = 0
        
        self.paused_events[job_id] = asyncio.Event()
        self.paused_events[job_id].set()
        
        # Send initial status message to user
        try:
            msg = await self.client.send_message(
                chat_id=user_id,
                text="🔄 Starting forwarding job..."
            )
            self.status_messages[job_id] = (user_id, msg.id)
            await update_job_progress(job_id, status_chat_id=user_id, status_message_id=msg.id)
        except Exception as e:
            logger.error(f"Failed to send status message to user {user_id}: {e}")
        
        # Load progress if this is an incomplete job
        progress_data = self.incomplete_jobs.get(job_id)
        if progress_data:
            forwarded_count = progress_data.get('forwarded', 0)
            last_msg_id = progress_data.get('last_msg_id', start_msg_id - 1)
            skipped_count = progress_data.get('skipped', 0)
            errors_total = progress_data.get('errors', 0)
            logger.info(f"Resuming job {job_id} from msg #{last_msg_id}")
            self.incomplete_jobs.pop(job_id, None)
        
        logger.info(f"Job {job_id}: Starting from msg #{start_msg_id}, total: {total}")
        logger.info(f"Source ID: {source_id}")
        logger.info(f"Destinations: {destinations}")
        
        # ============================================================
        # STEP 1: Verify access to the source channel
        # ============================================================
        try:
            chat = await self.client.get_chat(source_id)
            logger.info(f"✅ Access to channel: {chat.title} (ID: {chat.id})")
        except Exception as e:
            error_msg = f"❌ Cannot access source channel: {str(e)}"
            logger.error(error_msg)
            await self.client.send_message(
                chat_id=user_id,
                text=f"{error_msg}\n\nMake sure the bot is a member/admin of the source channel."
            )
            await complete_job(job_id, "failed")
            return
        
        # ============================================================
        # STEP 2: Calculate the range to fetch (NO LATEST CHECK!)
        # ============================================================
        # User wants: start_msg_id to start_msg_id + total - 1
        # Example: start_msg_id=20, total=3 → fetch 20, 21, 22
        
        current_id = start_msg_id
        
        # If total is "all" (999999), fetch up to a reasonable limit
        if total >= 999999:
            end_id = start_msg_id + 5000  # Fetch up to 5000 messages
            logger.info(f"📥 Forwarding ALL messages from #{start_msg_id} to #{end_id} (limited to 5000)")
        else:
            end_id = start_msg_id + total - 1
            logger.info(f"📥 Fetching messages from ID {current_id} to {end_id} (total: {total})")
        
        # ============================================================
        # STEP 3: Fetch and forward messages in batches
        # ============================================================
        batch_size = 50
        processed = 0
        album_buffer = {}
        max_fetched_id = current_id - 1
        
        while current_id <= end_id:
            if job_id not in self.running_jobs:
                logger.info(f"Job {job_id} stopped")
                break
            
            await self.paused_events[job_id].wait()
            
            # Calculate batch size
            remaining = end_id - current_id + 1
            batch = min(batch_size, remaining)
            message_ids = list(range(current_id, current_id + batch))
            
            logger.info(f"📦 Fetching batch: {message_ids[0]} to {message_ids[-1]} ({len(message_ids)} messages)")
            
            try:
                # Fetch messages by ID
                messages = await self.client.get_messages(source_id, message_ids)
                
                # Filter out None values (deleted/non-existent messages)
                messages = [m for m in messages if m is not None]
                
                if messages:
                    logger.info(f"✅ Fetched {len(messages)} messages in batch")
                    
                    # Sort ascending by ID (oldest first)
                    messages.sort(key=lambda m: m.id)
                    
                    # Process each message
                    for msg in messages:
                        if job_id not in self.running_jobs:
                            break
                        
                        await self.paused_events[job_id].wait()
                        
                        # Check if we should skip this message based on filter
                        if not self.should_forward_message(msg, filter_type, settings):
                            skipped_count += 1
                            max_fetched_id = max(max_fetched_id, msg.id)
                            logger.debug(f"Skipped message {msg.id} (filter)")
                            continue
                        
                        # Skip empty/service messages
                        if not msg.text and not msg.photo and not msg.video and not msg.document and \
                           not msg.audio and not msg.voice and not msg.sticker and not msg.animation and \
                           not msg.video_note and not msg.poll and not msg.contact and not msg.location and \
                           not msg.venue:
                            skipped_count += 1
                            max_fetched_id = max(max_fetched_id, msg.id)
                            logger.debug(f"Skipped message {msg.id} (empty/service)")
                            continue
                        
                        # Check if this is part of an album
                        if msg.media_group_id:
                            if msg.media_group_id not in album_buffer:
                                album_buffer[msg.media_group_id] = []
                            album_buffer[msg.media_group_id].append(msg)
                            logger.debug(f"Added message {msg.id} to album {msg.media_group_id}")
                            continue
                        
                        # Flush any pending albums first
                        if album_buffer:
                            for group_id, album_msgs in album_buffer.items():
                                if album_msgs:
                                    logger.info(f"📸 Sending album with {len(album_msgs)} messages (group {group_id})")
                                    for dest in destinations:
                                        success, retries = await self.send_album(
                                            dest['id'], album_msgs, settings,
                                            rate_limiter, settings.get('retry_enabled', True),
                                            settings.get('max_retries', 3)
                                        )
                                        if not success:
                                            errors_total += 1
                                            logger.warning(f"Failed to send album to {dest['id']}")
                                        retries_total += retries
                                        await rate_limiter.wait_with_delay(rate_limiter.get_delay())
                                    
                                    # Track progress for album
                                    for album_msg in album_msgs:
                                        max_fetched_id = max(max_fetched_id, album_msg.id)
                                    forwarded_count += 1  # Count album as one "message"
                                    processed += len(album_msgs)
                            album_buffer.clear()
                        
                        # Send single message
                        logger.info(f"📤 Forwarding message {msg.id} to {len(destinations)} destinations")
                        for dest in destinations:
                            success, retries = await self.send_single_message(
                                dest['id'], msg, settings,
                                rate_limiter, settings.get('retry_enabled', True),
                                settings.get('max_retries', 3)
                            )
                            if not success:
                                errors_total += 1
                                logger.warning(f"Failed to send message {msg.id} to {dest['id']}")
                            retries_total += retries
                            await rate_limiter.wait_with_delay(rate_limiter.get_delay())
                        
                        max_fetched_id = max(max_fetched_id, msg.id)
                        forwarded_count += 1
                        processed += 1
                        
                        # Update progress every 5 messages
                        if processed % 5 == 0:
                            progress = {
                                "last_id": max_fetched_id,
                                "forwarded": forwarded_count,
                                "skipped": skipped_count,
                                "errors": errors_total,
                                "started": start_time
                            }
                            self.save_progress(job_id, progress)
                            
                            await update_job_progress(
                                job_id, forwarded=forwarded_count,
                                errors=errors_total, retries=retries_total,
                                skipped=skipped_count, last_msg_id=max_fetched_id
                            )
                            
                            elapsed = time.time() - start_time
                            await self.update_user_status(
                                job_id, job_data, forwarded_count, skipped_count,
                                errors_total, max_fetched_id, total, delay, elapsed,
                                "RUNNING"
                            )
                    
                    # Flush any remaining albums after batch
                    if album_buffer:
                        for group_id, album_msgs in album_buffer.items():
                            if album_msgs:
                                logger.info(f"📸 Sending album with {len(album_msgs)} messages (group {group_id})")
                                for dest in destinations:
                                    success, retries = await self.send_album(
                                        dest['id'], album_msgs, settings,
                                        rate_limiter, settings.get('retry_enabled', True),
                                        settings.get('max_retries', 3)
                                    )
                                    if not success:
                                        errors_total += 1
                                    retries_total += retries
                                    await rate_limiter.wait_with_delay(rate_limiter.get_delay())
                                
                                for album_msg in album_msgs:
                                    max_fetched_id = max(max_fetched_id, album_msg.id)
                                forwarded_count += 1
                                processed += len(album_msgs)
                        album_buffer.clear()
                else:
                    logger.info(f"⚠️ No messages found in range {current_id} to {current_id + batch - 1}")
                
                # Move to next batch
                current_id += batch
                
            except FloodWait as e:
                logger.warning(f"⏳ FloodWait: {e.value}s")
                await asyncio.sleep(e.value + 5)
                continue
            except Exception as e:
                logger.error(f"❌ Error processing batch: {e}")
                current_id += batch
                continue
        
        # ============================================================
        # STEP 4: Job completed
        # ============================================================
        elapsed = time.time() - start_time
        await complete_job(job_id, "completed")
        self.delete_progress(job_id)
        
        # Final status update
        await self.update_user_status(
            job_id, job_data, forwarded_count, skipped_count,
            errors_total, max_fetched_id, total, delay, elapsed,
            "DONE", "✅", show_buttons=False
        )
        
        # Update admin log
        try:
            speed = calculate_speed(forwarded_count, elapsed)
            admin_logger = AdminLogger(self.client)
            await admin_logger.update_job_progress(
                admin_message_id, job_data, forwarded_count, total,
                speed, "0s", "✅", "Completed",
                f"\n❌ Errors: {errors_total}\n⏭ Skipped: {skipped_count}"
            )
        except Exception as e:
            logger.warning(f"Admin log final update failed: {e}")
        
        # Clean up
        if job_id in self.paused_events:
            del self.paused_events[job_id]
        if job_id in self.running_jobs:
            del self.running_jobs[job_id]
        if job_id in self.status_messages:
            del self.status_messages[job_id]
        
        logger.info(f"✅ Job {job_id} completed: {forwarded_count} forwarded, {skipped_count} skipped, {errors_total} errors")
    
    async def pause_job(self, job_id: int):
        if job_id in self.paused_events:
            self.paused_events[job_id].clear()
            await update_job_progress(job_id, status="paused")
            
            chat_id, message_id = self.status_messages.get(job_id, (None, None))
            if chat_id and message_id:
                try:
                    text = """⏸ PAUSED — tap Resume to continue
━━━━━━━━━━━━━━━━━━━━
[▶️ Resume]  [🛑 Stop]"""
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("▶️ Resume", callback_data=f"resume_job_{job_id}"),
                         InlineKeyboardButton("🛑 Stop", callback_data=f"stop_job_{job_id}")]
                    ])
                    await self.client.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=text,
                        reply_markup=keyboard
                    )
                except Exception as e:
                    logger.warning(f"Failed to update status message on pause: {e}")
    
    async def resume_job(self, job_id: int):
        if job_id in self.paused_events:
            self.paused_events[job_id].set()
            await update_job_progress(job_id, status="running")
            
            chat_id, message_id = self.status_messages.get(job_id, (None, None))
            if chat_id and message_id:
                try:
                    text = """🔄 RESUMED — continuing...
━━━━━━━━━━━━━━━━━━━━
[⏸️ Pause]  [🛑 Stop]"""
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("⏸️ Pause", callback_data=f"pause_job_{job_id}"),
                         InlineKeyboardButton("🛑 Stop", callback_data=f"stop_job_{job_id}")]
                    ])
                    await self.client.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=text,
                        reply_markup=keyboard
                    )
                except Exception as e:
                    logger.warning(f"Failed to update status message on resume: {e}")
    
    async def cancel_job(self, job_id: int):
        if job_id in self.running_jobs:
            self.running_jobs[job_id].cancel()
            await complete_job(job_id, "cancelled")
            self.delete_progress(job_id)
            
            chat_id, message_id = self.status_messages.get(job_id, (None, None))
            if chat_id and message_id:
                try:
                    await self.client.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text="🛑 Job stopped by user."
                    )
                except Exception as e:
                    logger.warning(f"Failed to update status message on cancel: {e}")
            
            if job_id in self.paused_events:
                del self.paused_events[job_id]
            if job_id in self.status_messages:
                del self.status_messages[job_id]