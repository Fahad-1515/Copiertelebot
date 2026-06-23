import re
from typing import Tuple, Optional
from pyrogram.types import Message

async def parse_destination_with_start(text: str) -> Tuple[Optional[str], int]:
    """Parse chat link and return (chat_id, start_msg_id)"""
    text = text.strip()
    start_msg_id = 1
    
    # Private channel with message: https://t.me/c/1234567890/200
    c_match = re.match(r'https?://t\.me/c/(\d+)(?:/(\d+))?', text)
    if c_match:
        chat_id = f"-100{c_match.group(1)}"
        if c_match.group(2):
            start_msg_id = int(c_match.group(2))
        return chat_id, start_msg_id
    
    # Username with message: https://t.me/username/200
    username_match = re.match(r'https?://t\.me/([a-zA-Z][a-zA-Z0-9_]{4,32})(?:/(\d+))?', text)
    if username_match:
        chat_id = f"@{username_match.group(1)}"
        if username_match.group(2):
            start_msg_id = int(username_match.group(2))
        return chat_id, start_msg_id
    
    # @username format
    if text.startswith('@'):
        return text, start_msg_id
    
    # Raw chat ID
    if text.startswith('-100') and text[1:].isdigit():
        return text, start_msg_id
    
    if text.lstrip('-').isdigit():
        return text, start_msg_id
    
    return None, 1

async def parse_chat_link(text: str) -> Optional[str]:
    """Parse various chat link formats and return chat ID (legacy)"""
    chat_id, _ = await parse_destination_with_start(text)
    return chat_id

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

async def parse_destination(text: str) -> Optional[str]:
    """Parse destination chat identifier (legacy)"""
    chat_id, _ = await parse_destination_with_start(text)
    return chat_id