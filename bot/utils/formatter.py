from typing import List, Dict
import time

def format_main_menu() -> str:
    return """👋 Welcome to Forward Bot!
━━━━━━━━━━━━━━━━━━━━
What would you like to do?
━━━━━━━━━━━━━━━━━━━━
[▶️ Start Forwarding]
[📋 My Jobs]  [⚙️ Settings]
[❓ Help]     [📊 Stats]"""

def format_source_confirmation(name: str, chat_id: str, members: int) -> str:
    return f"""✅ Source Detected!
━━━━━━━━━━━━━━━━━━━━
📢 Name: {name}
🆔 ID: {chat_id}
👥 Members: {members:,}
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
                              est_time: str) -> str:
    dest_text = "\n".join([f"     • {d.get('name', d['id'])}" for d in destinations[:5]])
    if len(destinations) > 5:
        dest_text += f"\n     • and {len(destinations)-5} more"
    
    return f"""🚀 Ready to Forward!
━━━━━━━━━━━━━━━━━━━━
📥 Source:       {source_name}
📤 Destinations: {len(destinations)} chats
{dest_text}
📩 Messages:     {total}
⏱️ Delay:        {delay}s/msg
🎛️ Filter:       {filter_type}
📋 Mode:         Copy (no forward tag)
⏰ Est. Time:    ~{est_time}
━━━━━━━━━━━━━━━━━━━━
[▶️ Start Now] [✏️ Edit Settings] [❌ Cancel]"""

def format_progress(forwarded: int, total: int, speed: float, 
                    delay: float, elapsed: float, eta: str, 
                    errors: int, retries: int) -> str:
    from bot.utils.progress import calculate_progress
    bar = calculate_progress(forwarded, total)
    
    return f"""🚀 Forwarding in Progress...
━━━━━━━━━━━━━━━━━━━━
📊 Progress:  {forwarded}/{total} {bar}
⚡ Speed:     {speed:.1f} msg/sec
⏱️ Delay:      {delay}s/msg
⏰ Elapsed:   {format_time_simple(elapsed)}
⏰ ETA:       ~{eta} remaining
❗ Errors:    {errors}
🔄 Retries:   {retries}
━━━━━━━━━━━━━━━━━━━━
[⏸️ Pause]  [❌ Cancel]"""

def format_completion(forwarded: int, total: int, delay: float, 
                      elapsed: float, speed: float, errors: int, 
                      retries: int) -> str:
    return f"""✅ Forwarding Complete!
━━━━━━━━━━━━━━━━━━━━
📨 Forwarded:  {forwarded}/{total}
⏱️ Delay Used: {delay}s/msg
⏰ Total Time: {format_time_simple(elapsed)}
⚡ Avg Speed:  {speed:.1f} msg/sec
❗ Errors:     {errors}
🔄 Retries:    {retries}
━━━━━━━━━━━━━━━━━━━━
[🔁 Forward Again] [🏠 Main Menu]"""

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