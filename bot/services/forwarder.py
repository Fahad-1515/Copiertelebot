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
from bot.core.db import update_job_progress, complete_job, get_job
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
                # ============================================================
                # TEXT MESSAGES
                # ============================================================
                if message.text and not message.photo and not message.video and not message.document:
                    text = self.clean_text(message.text, settings)
                    if text:
                        try:
                            await self.client.send_message(
                                chat_id=dest_chat,
                                text=text,
                                entities=message.entities
                            )
                        except Exception as e:
                            error_str = str(e)
                            if "ENTITY_BOUNDS_INVALID" in error_str or "entity" in error_str.lower():
                                logger.warning(f"Entity bounds invalid for msg {message.id}, sending without formatting")
                                await self.client.send_message(
                                    chat_id=dest_chat,
                                    text=text
                                )
                            else:
                                raise
                    return True, 0
                
                # ============================================================
                # PHOTOS
                # ============================================================
                elif message.photo:
                    caption = self.clean_text(message.caption or "", settings)
                    try:
                        await self.client.send_photo(
                            chat_id=dest_chat,
                            photo=message.photo.file_id,
                            caption=caption
                        )
                    except Exception as e:
                        error_str = str(e)
                        if "MEDIA_EMPTY" in error_str:
                            logger.warning(f"Media empty for photo {message.id}, skipping")
                            return True, 0
                        elif "MESSAGE_ID_INVALID" in error_str:
                            logger.warning(f"Message {message.id} no longer exists, skipping")
                            return True, 0
                        else:
                            raise
                    return True, 0
                
                # ============================================================
                # VIDEOS
                # ============================================================
                elif message.video:
                    caption = self.clean_text(message.caption or "", settings)
                    try:
                        await self.client.send_video(
                            chat_id=dest_chat,
                            video=message.video.file_id,
                            caption=caption,
                            duration=message.video.duration,
                            width=message.video.width,
                            height=message.video.height
                        )
                    except Exception as e:
                        error_str = str(e)
                        if "MEDIA_EMPTY" in error_str:
                            logger.warning(f"Media empty for video {message.id}, skipping")
                            return True, 0
                        elif "MESSAGE_ID_INVALID" in error_str:
                            logger.warning(f"Message {message.id} no longer exists, skipping")
                            return True, 0
                        else:
                            raise
                    return True, 0
                
                # ============================================================
                # DOCUMENTS / FILES
                # ============================================================
                elif message.document:
                    caption = self.clean_text(message.caption or "", settings)
                    try:
                        await self.client.send_document(
                            chat_id=dest_chat,
                            document=message.document.file_id,
                            caption=caption,
                            file_name=message.document.file_name
                        )
                    except Exception as e:
                        error_str = str(e)
                        if "MEDIA_EMPTY" in error_str:
                            logger.warning(f"Media empty for document {message.id}, skipping")
                            return True, 0
                        elif "MESSAGE_ID_INVALID" in error_str:
                            logger.warning(f"Message {message.id} no longer exists, skipping")
                            return True, 0
                        else:
                            raise
                    return True, 0
                
                # ============================================================
                # AUDIO
                # ============================================================
                elif message.audio:
                    caption = self.clean_text(message.caption or "", settings)
                    try:
                        await self.client.send_audio(
                            chat_id=dest_chat,
                            audio=message.audio.file_id,
                            caption=caption,
                            duration=message.audio.duration,
                            performer=message.audio.performer,
                            title=message.audio.title
                        )
                    except Exception as e:
                        error_str = str(e)
                        if "MEDIA_EMPTY" in error_str:
                            logger.warning(f"Media empty for audio {message.id}, skipping")
                            return True, 0
                        elif "MESSAGE_ID_INVALID" in error_str:
                            logger.warning(f"Message {message.id} no longer exists, skipping")
                            return True, 0
                        else:
                            raise
                    return True, 0
                
                # ============================================================
                # VOICE
                # ============================================================
                elif message.voice:
                    caption = self.clean_text(message.caption or "", settings)
                    try:
                        await self.client.send_voice(
                            chat_id=dest_chat,
                            voice=message.voice.file_id,
                            caption=caption,
                            duration=message.voice.duration
                        )
                    except Exception as e:
                        error_str = str(e)
                        if "MEDIA_EMPTY" in error_str:
                            logger.warning(f"Media empty for voice {message.id}, skipping")
                            return True, 0
                        elif "MESSAGE_ID_INVALID" in error_str:
                            logger.warning(f"Message {message.id} no longer exists, skipping")
                            return True, 0
                        else:
                            raise
                    return True, 0
                
                # ============================================================
                # STICKERS
                # ============================================================
                elif message.sticker:
                    try:
                        await self.client.send_sticker(
                            chat_id=dest_chat,
                            sticker=message.sticker.file_id
                        )
                    except Exception as e:
                        error_str = str(e)
                        if "MEDIA_EMPTY" in error_str:
                            logger.warning(f"Media empty for sticker {message.id}, skipping")
                            return True, 0
                        elif "MESSAGE_ID_INVALID" in error_str:
                            logger.warning(f"Message {message.id} no longer exists, skipping")
                            return True, 0
                        else:
                            raise
                    return True, 0
                
                # ============================================================
                # ANIMATIONS / GIFS
                # ============================================================
                elif message.animation:
                    caption = self.clean_text(message.caption or "", settings)
                    try:
                        await self.client.send_animation(
                            chat_id=dest_chat,
                            animation=message.animation.file_id,
                            caption=caption,
                            duration=message.animation.duration,
                            width=message.animation.width,
                            height=message.animation.height
                        )
                    except Exception as e:
                        error_str = str(e)
                        if "MEDIA_EMPTY" in error_str:
                            logger.warning(f"Media empty for animation {message.id}, skipping")
                            return True, 0
                        elif "MESSAGE_ID_INVALID" in error_str:
                            logger.warning(f"Message {message.id} no longer exists, skipping")
                            return True, 0
                        else:
                            raise
                    return True, 0
                
                # ============================================================
                # VIDEO NOTES
                # ============================================================
                elif message.video_note:
                    try:
                        await self.client.send_video_note(
                            chat_id=dest_chat,
                            video_note=message.video_note.file_id,
                            duration=message.video_note.duration,
                            length=message.video_note.length
                        )
                    except Exception as e:
                        error_str = str(e)
                        if "MEDIA_EMPTY" in error_str:
                            logger.warning(f"Media empty for video note {message.id}, skipping")
                            return True, 0
                        elif "MESSAGE_ID_INVALID" in error_str:
                            logger.warning(f"Message {message.id} no longer exists, skipping")
                            return True, 0
                        else:
                            raise
                    return True, 0
                
                # ============================================================
                # POLLS
                # ============================================================
                elif message.poll:
                    try:
                        await self.client.send_poll(
                            chat_id=dest_chat,
                            question=message.poll.question,
                            options=[opt.text for opt in message.poll.options],
                            is_anonymous=message.poll.is_anonymous,
                            type=message.poll.type,
                            allows_multiple_answers=message.poll.allows_multiple_answers
                        )
                    except Exception as e:
                        error_str = str(e)
                        if "MESSAGE_ID_INVALID" in error_str:
                            logger.warning(f"Message {message.id} no longer exists, skipping")
                            return True, 0
                        else:
                            raise
                    return True, 0
                
                # ============================================================
                # CONTACTS
                # ============================================================
                elif message.contact:
                    try:
                        await self.client.send_contact(
                            chat_id=dest_chat,
                            phone_number=message.contact.phone_number,
                            first_name=message.contact.first_name,
                            last_name=message.contact.last_name,
                            vcard=message.contact.vcard
                        )
                    except Exception as e:
                        error_str = str(e)
                        if "MESSAGE_ID_INVALID" in error_str:
                            logger.warning(f"Message {message.id} no longer exists, skipping")
                            return True, 0
                        else:
                            raise
                    return True, 0
                
                # ============================================================
                # LOCATIONS
                # ============================================================
                elif message.location:
                    try:
                        await self.client.send_location(
                            chat_id=dest_chat,
                            latitude=message.location.latitude,
                            longitude=message.location.longitude
                        )
                    except Exception as e:
                        error_str = str(e)
                        if "MESSAGE_ID_INVALID" in error_str:
                            logger.warning(f"Message {message.id} no longer exists, skipping")
                            return True, 0
                        else:
                            raise
                    return True, 0
                
                # ============================================================
                # VENUES
                # ============================================================
                elif message.venue:
                    try:
                        await self.client.send_venue(
                            chat_id=dest_chat,
                            latitude=message.venue.location.latitude,
                            longitude=message.venue.location.longitude,
                            title=message.venue.title,
                            address=message.venue.address,
                            foursquare_id=message.venue.foursquare_id
                        )
                    except Exception as e:
                        error_str = str(e)
                        if "MESSAGE_ID_INVALID" in error_str:
                            logger.warning(f"Message {message.id} no longer exists, skipping")
                            return True, 0
                        else:
                            raise
                    return True, 0
                
                # ============================================================
                # UNKNOWN TYPE - SKIP
                # ============================================================
                else:
                    logger.debug(f"Unknown message type for msg {message.id}, skipping")
                    return True, 0
                
            # ============================================================
            # FLOOD WAIT HANDLING
            # ============================================================
            except FloodWait as e:
                logger.warning(f"FloodWait: {e.value}s for {dest_chat}")
                await rate_limiter.handle_flood_wait(e.value)
                retries += 1
                if not retry_enabled or retries >= max_retries:
                    return False, retries
                continue
            
            # ============================================================
            # PERMISSION ERRORS
            # ============================================================
            except ChatWriteForbidden:
                logger.error(f"Cannot write to {dest_chat} - bot is not admin")
                return False, retries
            except MessageNotModified:
                return True, 0
            
            # ============================================================
            # RPC ERRORS
            # ============================================================
            except RPCError as e:
                error_str = str(e)
                if "INPUT_USER_DEACTIVATED" in error_str:
                    logger.warning(f"User {dest_chat} is deactivated, marking as failed")
                    return False, retries
                elif "USER_IS_BLOCKED" in error_str:
                    logger.warning(f"User {dest_chat} has blocked the bot")
                    return False, retries
                elif "CHAT_SEND_MEDIA_FORBIDDEN" in error_str:
                    logger.warning(f"Cannot send media to {dest_chat}")
                    return False, retries
                elif "MESSAGE_EMPTY" in error_str:
                    logger.warning(f"Empty message, skipping")
                    return True, 0
                elif "MESSAGE_ID_INVALID" in error_str:
                    logger.warning(f"Message ID invalid, skipping")
                    return True, 0
                elif "MEDIA_EMPTY" in error_str:
                    logger.warning(f"Media empty, skipping")
                    return True, 0
                else:
                    logger.error(f"RPCError forwarding to {dest_chat}: {e}")
                    if not retry_enabled or retries >= max_retries:
                        return False, retries
                    retries += 1
                    await asyncio.sleep(2 ** retries)
                    continue
            
            # ============================================================
            # GENERAL ERRORS
            # ============================================================
            except Exception as e:
                error_str = str(e)
                if "MEDIA_EMPTY" in error_str:
                    logger.warning(f"Media empty, skipping")
                    return True, 0
                elif "MESSAGE_ID_INVALID" in error_str or "message to forward not found" in error_str.lower():
                    logger.warning(f"Message no longer exists, skipping")
                    return True, 0
                else:
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
    
    async def update_realtime_status(self, job_id: int, message, dest_count: int, 
                                      forwarded: int, total: int):
        """Update real-time message transfer status in user's chat"""
        chat_id, message_id = self.status_messages.get(job_id, (None, None))
        if not chat_id or not message_id:
            return
        
        if message is None:
            text = f"""🔄 **STARTING FORWARDING**
━━━━━━━━━━━━━━━━━━━━
📤 **Source:** Loading...
📥 **Destinations:** {dest_count} chats
📩 **Messages:** 0/{total if total < 999999 else '∞'}
📊 **Progress:** ░░░░░░░░░░░░ 0%
━━━━━━━━━━━━━━━━━━━━
⏳ Fetching messages from source...
━━━━━━━━━━━━━━━━━━━━
[⏸️ Pause]  [🛑 Stop]"""
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⏸️ Pause", callback_data=f"pause_job_{job_id}"),
                 InlineKeyboardButton("🛑 Stop", callback_data=f"stop_job_{job_id}")]
            ])
            
            try:
                await self.client.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=text,
                    reply_markup=keyboard
                )
            except Exception as e:
                logger.warning(f"Failed to update real-time status: {e}")
            return
        
        # Determine message type
        if message.text:
            msg_type = "📝 Text"
        elif message.photo:
            msg_type = "🖼️ Photo"
        elif message.video:
            msg_type = "🎬 Video"
        elif message.document:
            msg_type = "📄 Document"
        elif message.audio:
            msg_type = "🎵 Audio"
        elif message.voice:
            msg_type = "🎙️ Voice"
        elif message.sticker:
            msg_type = "🏷️ Sticker"
        elif message.animation:
            msg_type = "🎞️ GIF"
        elif message.video_note:
            msg_type = "📹 Video Note"
        elif message.poll:
            msg_type = "📊 Poll"
        elif message.contact:
            msg_type = "📇 Contact"
        elif message.location:
            msg_type = "📍 Location"
        elif message.venue:
            msg_type = "🏪 Venue"
        else:
            msg_type = "📦 Other"
        
        if total > 0 and total < 999999:
            percent = int((forwarded / total) * 100)
            filled = int(12 * (forwarded / total))
            bar = "█" * filled + "░" * (12 - filled)
            progress_text = f"📊 **Progress:** {bar} {percent}%"
            msg_count = f"{forwarded}/{total}"
        else:
            progress_text = f"📊 **Forwarded:** {forwarded:,} messages"
            msg_count = f"{forwarded} sent"
        
        source_name = message.chat.title or message.chat.username or "Unknown"
        
        text = f"""🔄 **COPYING IN PROGRESS**
━━━━━━━━━━━━━━━━━━━━
📤 **Source:** {source_name}
📥 **Destinations:** {dest_count} chats
📩 **Messages:** {msg_count}
{progress_text}
━━━━━━━━━━━━━━━━━━━━
📨 **Last Transfer:**
   • ID: #{message.id}
   • Type: {msg_type}
   • Status: ✅ Sent
━━━━━━━━━━━━━━━━━━━━
[⏸️ Pause]  [🛑 Stop]"""
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏸️ Pause", callback_data=f"pause_job_{job_id}"),
             InlineKeyboardButton("🛑 Stop", callback_data=f"stop_job_{job_id}")]
        ])
        
        try:
            await self.client.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=keyboard
            )
        except MessageNotModified:
            pass
        except Exception as e:
            logger.warning(f"Failed to update real-time status: {e}")
    
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

    # ============================================================
    # run_forwarding_job method with real-time updates
    # ============================================================
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
        
        try:
            msg = await self.client.send_message(
                chat_id=user_id,
                text="🔄 Starting forwarding job..."
            )
            self.status_messages[job_id] = (user_id, msg.id)
            await update_job_progress(job_id, status_chat_id=user_id, status_message_id=msg.id)
        except Exception as e:
            logger.error(f"Failed to send status message to user {user_id}: {e}")
        
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
        # STEP 2: Calculate the range to fetch
        # ============================================================
        current_id = start_msg_id
        
        if total >= 999999:
            try:
                latest_msg = await self.client.get_messages(source_id, 1)
                if latest_msg:
                    end_id = latest_msg.id
                    total_messages = end_id - start_msg_id + 1
                    logger.info(f"📥 Forwarding ALL messages from #{start_msg_id} to #{end_id} (total: {total_messages} messages)")
                    job_data['total'] = total_messages
                    await self.client.send_message(
                        chat_id=user_id,
                        text=f"📥 Forwarding ALL messages from #{start_msg_id} to #{end_id} (total: {total_messages} messages)"
                    )
                else:
                    logger.error(f"No messages found in source {source_id}")
                    await self.client.send_message(
                        chat_id=user_id,
                        text="❌ No messages found in the source channel."
                    )
                    await complete_job(job_id, "failed")
                    return
            except Exception as e:
                logger.error(f"Failed to get latest message: {e}")
                await self.client.send_message(
                    chat_id=user_id,
                    text=f"❌ Failed to get latest message from source channel.\nError: {str(e)[:200]}"
                )
                await complete_job(job_id, "failed")
                return
        else:
            # YOUR LOGIC: end_id = start_msg_id + total
            end_id = start_msg_id + total
            total_messages = total + 1
            logger.info(f"📥 Fetching messages from ID {current_id} to {end_id} (total: {total_messages} messages)")
            job_data['total'] = total_messages
        
        if current_id > end_id:
            logger.info(f"No messages in range {current_id} to {end_id}")
            await self.client.send_message(
                chat_id=user_id,
                text=f"✅ No messages found from #{current_id} to #{end_id}."
            )
            await complete_job(job_id, "completed")
            return
        
        # ============================================================
        # STEP 3: Fetch and forward messages in batches
        # ============================================================
        batch_size = 50
        processed = 0
        album_buffer = {}
        max_fetched_id = current_id - 1
        
        await self.update_realtime_status(job_id, None, len(destinations), 0, total_messages)
        
        while current_id <= end_id:
            if job_id not in self.running_jobs:
                logger.info(f"Job {job_id} stopped")
                break
            
            await self.paused_events[job_id].wait()
            
            remaining = end_id - current_id + 1
            batch = min(batch_size, remaining)
            message_ids = list(range(current_id, current_id + batch))
            
            logger.info(f"📦 Fetching batch: {message_ids[0]} to {message_ids[-1]} ({len(message_ids)} messages)")
            
            try:
                messages = await self.client.get_messages(source_id, message_ids)
                messages = [m for m in messages if m is not None]
                
                if messages:
                    logger.info(f"✅ Fetched {len(messages)} messages in batch")
                    messages.sort(key=lambda m: m.id)
                    
                    for msg in messages:
                        if job_id not in self.running_jobs:
                            break
                        
                        await self.paused_events[job_id].wait()
                        
                        if not self.should_forward_message(msg, filter_type, settings):
                            skipped_count += 1
                            max_fetched_id = max(max_fetched_id, msg.id)
                            logger.debug(f"Skipped message {msg.id} (filter)")
                            continue
                        
                        if not msg.text and not msg.photo and not msg.video and not msg.document and \
                           not msg.audio and not msg.voice and not msg.sticker and not msg.animation and \
                           not msg.video_note and not msg.poll and not msg.contact and not msg.location and \
                           not msg.venue:
                            skipped_count += 1
                            max_fetched_id = max(max_fetched_id, msg.id)
                            logger.debug(f"Skipped message {msg.id} (empty/service)")
                            continue
                        
                        if msg.media_group_id:
                            if msg.media_group_id not in album_buffer:
                                album_buffer[msg.media_group_id] = []
                            album_buffer[msg.media_group_id].append(msg)
                            logger.debug(f"Added message {msg.id} to album {msg.media_group_id}")
                            continue
                        
                        if album_buffer:
                            for group_id, album_msgs in album_buffer.items():
                                if album_msgs:
                                    logger.info(f"📸 Sending album with {len(album_msgs)} messages (group {group_id})")
                                    for dest in destinations:
                                        dest_id = dest['id']
                                        success, retries = await self.send_album(
                                            dest_id, album_msgs, settings,
                                            rate_limiter, settings.get('retry_enabled', True),
                                            settings.get('max_retries', 3)
                                        )
                                        if not success:
                                            errors_total += 1
                                            logger.warning(f"Failed to send album to {dest_id}")
                                        retries_total += retries
                                        await rate_limiter.wait_with_delay(rate_limiter.get_delay())
                                    
                                    for album_msg in album_msgs:
                                        max_fetched_id = max(max_fetched_id, album_msg.id)
                                    forwarded_count += 1
                                    processed += len(album_msgs)
                                    
                                    await self.update_realtime_status(
                                        job_id, album_msgs[0], len(destinations), 
                                        forwarded_count, total_messages
                                    )
                            album_buffer.clear()
                        
                        logger.info(f"📤 Forwarding message {msg.id} to {len(destinations)} destinations")
                        for dest in destinations:
                            dest_id = dest['id']
                            success, retries = await self.send_single_message(
                                dest_id, msg, settings,
                                rate_limiter, settings.get('retry_enabled', True),
                                settings.get('max_retries', 3)
                            )
                            if not success:
                                errors_total += 1
                                logger.warning(f"Failed to send message {msg.id} to {dest_id}")
                            else:
                                logger.info(f"✅ Sent message {msg.id} to {dest_id}")
                            retries_total += retries
                            await rate_limiter.wait_with_delay(rate_limiter.get_delay())
                        
                        max_fetched_id = max(max_fetched_id, msg.id)
                        forwarded_count += 1
                        processed += 1
                        
                        await self.update_realtime_status(
                            job_id, msg, len(destinations), 
                            forwarded_count, total_messages
                        )
                        
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
                                errors_total, max_fetched_id, total_messages, delay, elapsed,
                                "RUNNING"
                            )
                    
                    if album_buffer:
                        for group_id, album_msgs in album_buffer.items():
                            if album_msgs:
                                logger.info(f"📸 Sending album with {len(album_msgs)} messages (group {group_id})")
                                for dest in destinations:
                                    dest_id = dest['id']
                                    success, retries = await self.send_album(
                                        dest_id, album_msgs, settings,
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
                                
                                await self.update_realtime_status(
                                    job_id, album_msgs[0], len(destinations), 
                                    forwarded_count, total_messages
                                )
                        album_buffer.clear()
                else:
                    logger.info(f"⚠️ No messages found in range {current_id} to {current_id + batch - 1}")
                
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
        
        await self.update_user_status(
            job_id, job_data, forwarded_count, skipped_count,
            errors_total, max_fetched_id, total_messages, delay, elapsed,
            "DONE", "✅", show_buttons=False
        )
        
        try:
            speed = calculate_speed(forwarded_count, elapsed)
            admin_logger = AdminLogger(self.client)
            await admin_logger.send_job_completed(
                admin_message_id, job_data, forwarded_count, 
                total_messages, errors_total, skipped_count, elapsed, speed
            )
        except Exception as e:
            logger.warning(f"Admin log final update failed: {e}")
        
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
            
            job_data = await get_job(job_id)
            if job_data:
                try:
                    admin_logger = AdminLogger(self.client)
                    await admin_logger.send_pause_notification(
                        job_id,
                        {"user_id": job_data['user_id'], "source_name": job_data['source_name']},
                        job_data.get('forwarded', 0),
                        job_data.get('total', 0)
                    )
                except Exception as e:
                    logger.warning(f"Admin pause notification failed: {e}")
            
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
            
            job_data = await get_job(job_id)
            if job_data:
                try:
                    admin_logger = AdminLogger(self.client)
                    await admin_logger.send_resume_notification(
                        job_id,
                        {"user_id": job_data['user_id'], "source_name": job_data['source_name']},
                        job_data.get('forwarded', 0),
                        job_data.get('total', 0)
                    )
                except Exception as e:
                    logger.warning(f"Admin resume notification failed: {e}")
            
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
            
            job_data = await get_job(job_id)
            if job_data:
                try:
                    admin_logger = AdminLogger(self.client)
                    await admin_logger.send_cancel_notification(
                        job_id,
                        {"user_id": job_data['user_id'], "source_name": job_data['source_name']},
                        job_data.get('forwarded', 0),
                        job_data.get('total', 0)
                    )
                except Exception as e:
                    logger.warning(f"Admin cancel notification failed: {e}")
            
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