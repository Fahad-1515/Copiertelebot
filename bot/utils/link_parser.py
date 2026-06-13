import re
from pyrogram.types import Message

async def parse_chat_link(text: str) -> str:
    """Parse various chat link formats and return chat ID"""
    text = text.strip()
    
    # Private channel: https://t.me/c/1234567890/5
    c_match = re.match(r'https?://t\.me/c/(\d+)(?:/\d+)?', text)
    if c_match:
        return f"-100{c_match.group(1)}"
    
    # Username: https://t.me/username
    username_match = re.match(r'https?://t\.me/([a-zA-Z][a-zA-Z0-9_]{4,32})', text)
    if username_match:
        return f"@{username_match.group(1)}"
    
    # @username format
    if text.startswith('@'):
        return text
    
    # Raw chat ID
    if text.startswith('-100') and text[1:].isdigit():
        return text
    
    if text.lstrip('-').isdigit():
        return text
    
    return None

async def get_chat_info(client, chat_id: str):
    """Get chat name and member count"""
    try:
        chat = await client.get_chat(chat_id)
        member_count = 0
        try:
            member_count = await client.get_chat_members_count(chat_id)
        except:
            pass
        return chat.title or chat.first_name, member_count
    except:
        return None, None

async def parse_destination(text: str) -> str:
    """Parse destination chat identifier"""
    text = text.strip()
    
    # Remove /done command if present
    if text.lower() == '/done':
        return None
    
    # Private channel
    c_match = re.match(r'https?://t\.me/c/(\d+)(?:/\d+)?', text)
    if c_match:
        return f"-100{c_match.group(1)}"
    
    # Username
    username_match = re.match(r'https?://t\.me/([a-zA-Z][a-zA-Z0-9_]{4,32})', text)
    if username_match:
        return f"@{username_match.group(1)}"
    
    # @username
    if text.startswith('@'):
        return text
    
    # Raw ID
    if text.lstrip('-').isdigit():
        return text
    
    return None