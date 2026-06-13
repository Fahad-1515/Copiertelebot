from pyrogram import Client
from pyrogram.types import Message
from bot.core.config import Config

class AdminLogger:
    def __init__(self, client: Client):
        self.client = client
        self.admin_group = Config.ADMIN_LOG_GROUP_ID
    
    async def send_job_start(self, user_id: int, username: str, source_name: str,
                             destinations: list, total: int, delay: float, 
                             filter_type: str) -> int:
        dest_text = "\n     • ".join([d.get('name', d['id']) for d in destinations[:5]])
        if len(destinations) > 5:
            dest_text += f"\n     • and {len(destinations)-5} more"
        
        text = f"""🔔 NEW JOB STARTED
━━━━━━━━━━━━━━━━━━━━
👤 User:         {username or f"ID: {user_id}"}
📥 Source:       {source_name}
📤 Destinations: {len(destinations)} chats
     • {dest_text}
📩 Messages:     {total}
⏱️ Delay:        {delay}s/msg
🎛️ Filter:       {filter_type}
🕐 Started:      {get_current_time()}
⚙️ Status:       🟢 Running
━━━━━━━━━━━━━━━━━━━━"""
        
        msg = await self.client.send_message(self.admin_group, text)
        return msg.id
    
    async def update_job_progress(self, message_id: int, job_data: dict, 
                                   forwarded: int, total: int, speed: float,
                                   eta: str, status_emoji: str = "🟢", 
                                   status_text: str = "Running",
                                   additional_info: str = ""):
        dest_text = "\n     • ".join([d.get('name', d['id']) for d in job_data['destinations'][:5]])
        
        text = f"""🔔 JOB IN PROGRESS
━━━━━━━━━━━━━━━━━━━━
👤 User:         {job_data.get('username', f"ID: {job_data['user_id']}")}
📥 Source:       {job_data['source_name']}
📤 Destinations: {len(job_data['destinations'])} chats
     • {dest_text}
📩 Messages:     {job_data['total']}
⏱️ Delay:        {job_data['delay_used']}s/msg
🎛️ Filter:       {job_data['filter_type']}
🕐 Started:      {format_time_short(job_data.get('started_at', 0))}
━━━━━━━━━━━━━━━━━━━━
📊 Progress: {forwarded}/{total} ({int(forwarded/total*100)}%)
⚡ Speed:    {speed:.1f} msg/sec
⏰ ETA:      ~{eta}
{additional_info}
⚙️ Status:  {status_emoji} {status_text}
━━━━━━━━━━━━━━━━━━━━"""
        
        await self.client.edit_message_text(self.admin_group, message_id, text)
    
    async def send_new_user_notification(self, user_id: int, username: str, 
                                          first_name: str):
        text = f"""👋 NEW USER JOINED
━━━━━━━━━━━━━━━━━━━━
👤 Name:     {first_name}
🔗 Username: @{username if username else 'No username'}
🆔 ID:       {user_id}
🕐 Joined:   {get_current_time()}
━━━━━━━━━━━━━━━━━━━━"""
        
        await self.client.send_message(self.admin_group, text)

def get_current_time() -> str:
    import time
    return time.strftime("%H:%M:%S")

def format_time_short(timestamp) -> str:
    if not timestamp:
        return "Unknown"
    try:
        import time
        if isinstance(timestamp, (int, float)):
            return time.strftime("%H:%M:%S", time.localtime(timestamp))
        return timestamp
    except:
        return "Unknown"