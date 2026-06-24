from typing import List, Dict
import time

def format_main_menu() -> str:
    return """👋 Welcome to Forward Bot!
━━━━━━━━━━━━━━━━━━━━
What would you like to do?
━━━━━━━━━━━━━━━━━━━━
[▶️ Start Forwarding]
[📋 My Jobs]  [⚙️ Settings]
[📜 History]  [📊 Stats]"""

def format_source_confirmation(name: str, chat_id: str, members: int, start_msg_id: int = 1) -> str:
    return f"""✅ Source Detected!
━━━━━━━━━━━━━━━━━━━━
📢 Name: {name}
🆔 ID: {chat_id}
👥 Members: {members:,}
📍 Starting from msg #{start_msg_id}
━━━━━━━━━━━━━━━━━━━━
[✅ Confirm] [🔄 Change Source]"""

def format_destinations_list(destinations: List[Dict]) -> str:
    if not destinations:
        return "No destinations added yet."
    
    text = "📋 Destinations Saved:\n━━━━━━━━━━━━━━━━━━━━\n"
    for i, dest in enumerate(destinations, 1):
        text += f"{i}. {dest.get('name', dest['id'])}\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n[✅ Confirm] [➕ Add More] [❌ Remove One]"
    return text

def format_final_confirmation(source_name: str, destinations: List[Dict], 
                              total: int, delay: float, filter_type: str,
                              start_msg_id: int = 1) -> str:
    dest_text = "\n".join([f"     • {d.get('name', d['id'])}" for d in destinations[:5]])
    if len(destinations) > 5:
        dest_text += f"\n     • and {len(destinations)-5} more"
    
    # Show message count with range (YOUR LOGIC: end = start + total)
    if total >= 999999:
        msg_text = "ALL (to the end)"
    else:
        end_msg_id = start_msg_id + total  # YOUR LOGIC: start + input = end
        total_msgs = total + 1  # Total messages = input + 1
        msg_text = f"{total_msgs} (#{start_msg_id} → #{end_msg_id})"
    
    return f"""🚀 Ready to Forward!
━━━━━━━━━━━━━━━━━━━━
📥 Source:       {source_name}
📍 Starting:     msg #{start_msg_id}
📤 Destinations: {len(destinations)} chats
{dest_text}
📩 Messages:     {msg_text}
⏱️ Delay:        {delay}s/msg
🎛️ Filter:       {filter_type}
📋 Mode:         Copy (no forward tag)
━━━━━━━━━━━━━━━━━━━━
[▶️ Start Now] [✏️ Edit Settings] [❌ Cancel]"""

def format_time_simple(seconds: float) -> str:
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