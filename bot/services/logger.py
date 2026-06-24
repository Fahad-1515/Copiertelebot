from pyrogram import Client
from pyrogram.types import Message
from bot.core.config import Config
import time
from typing import Dict, Optional, List

class AdminLogger:
    def __init__(self, client: Client):
        self.client = client
        self.admin_group = Config.ADMIN_LOG_GROUP_ID
        self.bot_info = None
        self.start_time = time.time()
        
        # Per-user live messages: user_id -> message_id
        self.user_live_messages: Dict[int, int] = {}
        
        # User sessions
        self.user_sessions: Dict[int, Dict] = {}
        
        # Completed/Failed logs (keep last 100)
        self.log_message_ids: List[int] = []
        self.MAX_LOGS = 100
    
    async def init_bot_info(self):
        if not self.bot_info:
            try:
                self.bot_info = await self.client.get_me()
            except Exception as e:
                print(f"Failed to get bot info: {e}")
                self.bot_info = type('obj', (object,), {
                    'username': 'Unknown',
                    'first_name': 'Bot',
                    'id': 0
                })()
    
    def get_message_type(self, message) -> str:
        if message.text:
            return "📝 Text"
        elif message.photo:
            return "🖼️ Photo"
        elif message.video:
            return "🎬 Video"
        elif message.document:
            return "📄 Document"
        elif message.audio:
            return "🎵 Audio"
        elif message.voice:
            return "🎙️ Voice"
        elif message.sticker:
            return "🏷️ Sticker"
        elif message.animation:
            return "🎞️ GIF"
        elif message.video_note:
            return "📹 Video Note"
        else:
            return "📦 Other"
    
    def get_transfer_status(self, forwarded: int, total: int, errors: int) -> str:
        if total <= 0:
            return "⏳ Waiting..."
        if forwarded >= total and errors == 0:
            return "✅ COMPLETED"
        elif forwarded >= total and errors > 0:
            return "⚠️ COMPLETED WITH ERRORS"
        elif errors > 0 and forwarded > 0:
            return "⚠️ PARTIAL (with errors)"
        elif forwarded > 0:
            return "🔄 IN PROGRESS"
        else:
            return "⏳ STARTING"
    
    async def update_user_live_message(self, user_id: int, user_data: Dict):
        """Update or create live message for a specific user"""
        if not self.admin_group:
            return
        
        # Use the stored username (already formatted with @)
        username = user_data.get('username', f"User{user_id}")
        
        # Determine status
        if user_data.get('active_job'):
            status = "🟢 ACTIVE"
        elif user_data.get('job_count', 0) > 0:
            status = "🟡 IDLE"
        else:
            status = "⚪ NEW"
        
        # Build live message for this user
        if user_data.get('active_job'):
            job = user_data['active_job']
            progress = f"{job['forwarded']}/{job['total']}"
            percent = int((job['forwarded'] / job['total']) * 100) if job['total'] > 0 else 0
            
            filled = int(10 * (job['forwarded'] / job['total'])) if job['total'] > 0 else 0
            bar = "█" * filled + "░" * (10 - filled)
            
            elapsed = time.time() - job['started_at']
            elapsed_str = format_time_short(elapsed)
            
            transfer_status = self.get_transfer_status(
                job['forwarded'], 
                job['total'], 
                job.get('errors', 0)
            )
            
            text = f"""👤 **{username}** {status}
━━━━━━━━━━━━━━━━━━━━
📥 **Source:** {job['source'][:30]}
📤 **Dest:** {len(job.get('destinations', []))} chats
📊 **Progress:** {bar} {percent}% ({progress})
⏱️ **Running:** {elapsed_str} | ⚡ {job.get('speed', 0):.1f} msg/min
📊 **Status:** {transfer_status}"""
            
            if job.get('last_transfer'):
                last = job['last_transfer']
                text += f"\n📨 **Last:** #{last.get('id', 'N/A')} {last.get('type', 'Unknown')}"
            
            if job.get('errors', 0) > 0:
                text += f" | ❌ {job['errors']} errors"
            
            if job.get('status') == 'paused':
                text += "\n⏸️ **PAUSED**"
            
            text += f"\n🕐 **Updated:** {get_current_time()}"
        
        else:
            # User is idle or new - show summary
            if user_data.get('job_count', 0) > 0:
                text = f"""👤 **{username}** {status}
━━━━━━━━━━━━━━━━━━━━
📊 **Jobs Done:** {user_data.get('job_count', 0)}
📨 **Forwarded:** {user_data.get('total_forwarded', 0):,} msgs"""
                if user_data.get('total_errors', 0) > 0:
                    text += f"\n❌ **Errors:** {user_data.get('total_errors', 0)}"
                text += f"\n🕐 **Last Active:** {get_current_time()}"
            else:
                text = f"""👤 **{username}** {status}
━━━━━━━━━━━━━━━━━━━━
📊 No jobs yet - waiting to start"""
        
        # Add user ID for reference
        text += f"\n🆔 `{user_id}`"
        
        # Send or edit the message
        try:
            if user_id in self.user_live_messages:
                # Edit existing message
                await self.client.edit_message_text(
                    self.admin_group,
                    self.user_live_messages[user_id],
                    text
                )
            else:
                # Send new message
                msg = await self.client.send_message(
                    self.admin_group,
                    text
                )
                self.user_live_messages[user_id] = msg.id
                self.log_message_ids.append(msg.id)
        except Exception as e:
            # If edit fails (message deleted), send new one
            try:
                msg = await self.client.send_message(
                    self.admin_group,
                    text
                )
                self.user_live_messages[user_id] = msg.id
                self.log_message_ids.append(msg.id)
            except Exception as e2:
                print(f"Failed to update live message for user {user_id}: {e2}")
    
    async def update_live_dashboard(self):
        """Update all users' live messages"""
        if not self.admin_group:
            return
        
        if not self.bot_info:
            await self.init_bot_info()
        
        # Update each user's live message
        for user_id, user_data in self.user_sessions.items():
            await self.update_user_live_message(user_id, user_data)
    
    async def send_final_log(self, user_id: int, user_data: Dict, job_data: Dict,
                              status: str, error: str = ""):
        """Send final Completed or Failed log and delete live message"""
        username = user_data.get('username', f"User{user_id}")
        source_name = job_data.get('source_name', 'Unknown')
        
        # Delete the live message
        if user_id in self.user_live_messages:
            try:
                await self.client.delete_messages(
                    self.admin_group,
                    self.user_live_messages[user_id]
                )
                del self.user_live_messages[user_id]
            except Exception as e:
                print(f"Failed to delete live message for user {user_id}: {e}")
        
        # Build final log based on status
        if status == "completed":
            forwarded = job_data.get('forwarded', 0)
            total = job_data.get('total', 0)
            errors = job_data.get('errors', 0)
            skipped = job_data.get('skipped', 0)
            elapsed = job_data.get('elapsed', 0)
            speed = job_data.get('speed', 0)
            
            dest_text = ", ".join([d.get('name', d['id']) for d in job_data.get('destinations', [])[:3]])
            if len(job_data.get('destinations', [])) > 3:
                dest_text += f" +{len(job_data.get('destinations', []))-3} more"
            
            if errors == 0:
                status_emoji = "🎉"
                status_text = "✅ COMPLETED"
            else:
                status_emoji = "⚠️"
                status_text = "⚠️ COMPLETED WITH ERRORS"
            
            final_msg = f"""{status_emoji} **JOB COMPLETED**
━━━━━━━━━━━━━━━━━━━━
👤 **User:** {username}
📥 **Source:** {source_name}
📤 **Dest:** {dest_text}
━━━━━━━━━━━━━━━━━━━━
✅ **Forwarded:** {forwarded:,} msgs
⏭ **Skipped:** {skipped:,}
❌ **Errors:** {errors:,}
📊 **Success Rate:** {((forwarded - errors) / forwarded * 100) if forwarded > 0 else 0:.1f}%
━━━━━━━━━━━━━━━━━━━━
⏱️ **Time Taken:** {format_time_short(elapsed)}
⚡ **Avg Speed:** {speed:.2f} msg/sec
━━━━━━━━━━━━━━━━━━━━
📊 **Status:** {status_text}
🕐 **Completed:** {get_current_time()}
━━━━━━━━━━━━━━━━━━━━"""
        
        elif status == "failed":
            final_msg = f"""🔴 **JOB FAILED**
━━━━━━━━━━━━━━━━━━━━
👤 **User:** {username}
📥 **Source:** {source_name}
❌ **Error:** {error[:200]}
🕐 **Failed:** {get_current_time()}
━━━━━━━━━━━━━━━━━━━━
📊 **Status:** ❌ FAILED
━━━━━━━━━━━━━━━━━━━━"""
        
        elif status == "cancelled":
            forwarded = job_data.get('forwarded', 0)
            final_msg = f"""🛑 **JOB CANCELLED**
━━━━━━━━━━━━━━━━━━━━
👤 **User:** {username}
📥 **Source:** {source_name}
📩 **Forwarded:** {forwarded:,} msgs
🕐 **Cancelled:** {get_current_time()}
━━━━━━━━━━━━━━━━━━━━
📊 **Status:** ❌ CANCELLED
━━━━━━━━━━━━━━━━━━━━"""
        
        else:
            return
        
        # Send final log
        try:
            msg = await self.client.send_message(self.admin_group, final_msg)
            self.log_message_ids.append(msg.id)
            await self.cleanup_old_logs()
        except Exception as e:
            print(f"Failed to send final log: {e}")
    
    async def cleanup_old_logs(self):
        """Keep only last 100 log messages"""
        try:
            log_count = len(self.log_message_ids)
            
            if log_count > self.MAX_LOGS:
                to_delete = self.log_message_ids[:-(self.MAX_LOGS)]
                
                for msg_id in to_delete:
                    try:
                        # Don't delete live messages
                        if msg_id not in self.user_live_messages.values():
                            await self.client.delete_messages(
                                self.admin_group,
                                msg_id
                            )
                    except Exception as e:
                        print(f"Failed to delete message {msg_id}: {e}")
                
                self.log_message_ids = self.log_message_ids[-self.MAX_LOGS:]
                
        except Exception as e:
            print(f"Cleanup failed: {e}")
    
    async def send_new_user_notification(self, user_id: int, username: str, 
                                          first_name: str):
        """Add new user and create live message"""
        # Use username if available, otherwise use first_name
        display_name = f"@{username}" if username else first_name
        
        self.user_sessions[user_id] = {
            'username': display_name,
            'first_name': first_name,
            'job_count': 0,
            'total_forwarded': 0,
            'total_errors': 0,
            'active_job': None,
            'first_seen': time.time(),
            'last_activity': time.time()
        }
        await self.update_live_dashboard()
    
    async def send_job_start(self, user_id: int, username: str, source_name: str,
                             destinations: list, total: int, delay: float, 
                             filter_type: str) -> int:
        # Use username if available, otherwise use first_name
        username_display = f"@{username}" if username else f"User{user_id}"
        
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {
                'username': username_display,
                'first_name': username_display,
                'job_count': 0,
                'total_forwarded': 0,
                'total_errors': 0,
                'active_job': None,
                'first_seen': time.time(),
                'last_activity': time.time()
            }
        
        self.user_sessions[user_id]['job_count'] += 1
        self.user_sessions[user_id]['last_activity'] = time.time()
        
        job_data = {
            'user_id': user_id,
            'username': username_display,
            'source': source_name,
            'dest_count': len(destinations),
            'destinations': destinations,
            'total': total,
            'forwarded': 0,
            'errors': 0,
            'started_at': time.time(),
            'delay': delay,
            'filter': filter_type,
            'speed': 0,
            'status': 'running',
            'last_transfer': None
        }
        
        self.user_sessions[user_id]['active_job'] = job_data
        await self.update_live_dashboard()
        return 0
    
    async def update_job_progress(self, message_id: int, job_data: dict, 
                                   forwarded: int, total: int, speed: float,
                                   eta: str, status_emoji: str = "🟢", 
                                   status_text: str = "Running",
                                   additional_info: str = ""):
        user_id = job_data.get('user_id')
        
        if user_id in self.user_sessions and self.user_sessions[user_id].get('active_job'):
            job = self.user_sessions[user_id]['active_job']
            job['forwarded'] = forwarded
            if additional_info and additional_info.isdigit():
                job['errors'] = int(additional_info)
            job['speed'] = speed * 60
            job['status'] = 'running' if status_text.lower() != 'paused' else 'paused'
            self.user_sessions[user_id]['last_activity'] = time.time()
            await self.update_live_dashboard()
    
    async def update_realtime_transfer(self, user_id: int, message, 
                                        forwarded: int, total: int,
                                        dest_count: int, errors: int = 0):
        if user_id not in self.user_sessions:
            return
        
        user = self.user_sessions[user_id]
        if not user.get('active_job'):
            return
        
        job = user['active_job']
        transfer_status = self.get_transfer_status(forwarded, total, errors)
        
        job['forwarded'] = forwarded
        job['errors'] = errors
        job['last_transfer'] = {
            'id': message.id,
            'type': self.get_message_type(message),
            'time': time.time(),
            'status': transfer_status
        }
        
        elapsed = time.time() - job['started_at']
        if elapsed > 0:
            job['speed'] = (forwarded / elapsed) * 60
        
        self.user_sessions[user_id]['last_activity'] = time.time()
        await self.update_live_dashboard()
    
    async def send_job_completed(self, message_id: int, job_data: dict, 
                                  forwarded: int, total: int, 
                                  errors: int, skipped: int,
                                  elapsed: float, speed: float):
        user_id = job_data.get('user_id')
        
        if user_id in self.user_sessions:
            # Update user stats
            self.user_sessions[user_id]['total_forwarded'] += forwarded
            self.user_sessions[user_id]['total_errors'] += errors
            self.user_sessions[user_id]['active_job'] = None
            self.user_sessions[user_id]['last_activity'] = time.time()
            
            # Update job data with completion info
            job_data['forwarded'] = forwarded
            job_data['total'] = total
            job_data['errors'] = errors
            job_data['skipped'] = skipped
            job_data['elapsed'] = elapsed
            job_data['speed'] = speed
            
            # Send final completed log
            await self.send_final_log(user_id, self.user_sessions[user_id], job_data, "completed")
            
            # Update live message (will show IDLE status)
            await self.update_live_dashboard()
    
    async def send_pause_notification(self, job_id: int, job_data: dict, 
                                       forwarded: int, total: int):
        user_id = job_data.get('user_id')
        if user_id in self.user_sessions and self.user_sessions[user_id].get('active_job'):
            self.user_sessions[user_id]['active_job']['status'] = 'paused'
            self.user_sessions[user_id]['last_activity'] = time.time()
            await self.update_live_dashboard()
    
    async def send_resume_notification(self, job_id: int, job_data: dict,
                                        forwarded: int, total: int):
        user_id = job_data.get('user_id')
        if user_id in self.user_sessions and self.user_sessions[user_id].get('active_job'):
            self.user_sessions[user_id]['active_job']['status'] = 'running'
            self.user_sessions[user_id]['last_activity'] = time.time()
            await self.update_live_dashboard()
    
    async def send_cancel_notification(self, job_id: int, job_data: dict,
                                        forwarded: int, total: int):
        user_id = job_data.get('user_id')
        
        if user_id in self.user_sessions:
            job_data['forwarded'] = forwarded
            job_data['total'] = total
            
            # Send cancelled log
            await self.send_final_log(user_id, self.user_sessions[user_id], job_data, "cancelled")
            
            self.user_sessions[user_id]['active_job'] = None
            self.user_sessions[user_id]['last_activity'] = time.time()
            
            # Update live message (will show IDLE status)
            await self.update_live_dashboard()
    
    async def send_failed_notification(self, user_id: int, username: str,
                                        source_name: str, error: str):
        """Send FAILED job notification"""
        if user_id not in self.user_sessions:
            return
        
        username_display = f"@{username}" if username else f"User{user_id}"
        
        job_data = {
            'user_id': user_id,
            'username': username_display,
            'source_name': source_name,
            'destinations': [],
            'forwarded': 0,
            'total': 0
        }
        
        # Send failed log
        await self.send_final_log(user_id, self.user_sessions[user_id], job_data, "failed", error)
        
        # Update user
        self.user_sessions[user_id]['total_errors'] += 1
        self.user_sessions[user_id]['active_job'] = None
        self.user_sessions[user_id]['last_activity'] = time.time()
        
        await self.update_live_dashboard()
    
    async def send_error_notification(self, user_id: int, username: str,
                                       source_name: str, error: str):
        if user_id in self.user_sessions:
            self.user_sessions[user_id]['total_errors'] += 1
            self.user_sessions[user_id]['last_activity'] = time.time()
        await self.update_live_dashboard()

def get_current_time() -> str:
    return time.strftime("%H:%M:%S")

def format_time_short(seconds: float) -> str:
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"