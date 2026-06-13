import re
import asyncio
from pyrogram import Client

# Your bot credentials (from .env)
API_ID = 19059105
API_HASH = "2d429e47f268938da672c5e33348ef51"
BOT_TOKEN = "8727581309:AAFPNDInOIpm8Egxo0HTTLxCijwWUdCQRxw"

async def get_chat_id_from_link(link: str):
    """Extract chat ID from Telegram link"""
    
    # Parse the link
    match = re.match(r'https?://t\.me/(?:c/)?([^/]+)(?:/(\d+))?', link)
    if not match:
        print("❌ Invalid Telegram link")
        return None
    
    username_or_id = match.group(1)
    message_id = match.group(2)
    
    app = Client("get_id", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
    await app.start()
    
    try:
        # Try to resolve as username
        if not username_or_id.startswith('c'):
            chat = await app.get_chat(username_or_id)
            print(f"\n✅ Channel/Group found!")
            print(f"📌 Name: {chat.title}")
            print(f"🆔 Chat ID: {chat.id}")
            print(f"📝 Type: {chat.type}")
            
            if message_id:
                print(f"📨 Message ID: {message_id}")
                print(f"🔗 Full reference: {chat.id}/{message_id}")
            
            return chat.id
        
        # Handle private channel format: t.me/c/1234567890/5
        elif username_or_id.isdigit():
            chat_id = int(f"-100{username_or_id}")
            print(f"\n✅ Private channel found!")
            print(f"🆔 Chat ID: {chat_id}")
            if message_id:
                print(f"📨 Message ID: {message_id}")
                print(f"🔗 Full reference: {chat_id}/{message_id}")
            return chat_id
            
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nPossible reasons:")
        print("• The channel/group doesn't exist")
        print("• Bot is not a member (for private channels)")
        print("• Invalid link format")
        
    finally:
        await app.stop()
    
    return None

async def main():
    print("=" * 50)
    print("TELEGRAM CHAT ID EXTRACTOR")
    print("=" * 50)
    print("\nEnter a Telegram channel/group link:")
    print("Examples:")
    print("  • https://t.me/username")
    print("  • https://t.me/username/5")
    print("  • https://t.me/c/1234567890/5")
    print("  • @username")
    print("\nType 'quit' to exit\n")
    
    while True:
        link = input("🔗 Enter link: ").strip()
        
        if link.lower() == 'quit':
            print("\nGoodbye!")
            break
        
        if not link:
            print("❌ Please enter a link\n")
            continue
        
        # Add https:// if missing
        if not link.startswith('http') and not link.startswith('@'):
            link = 'https://t.me/' + link.lstrip('/')
        
        print(f"\n🔍 Processing: {link}\n")
        chat_id = await get_chat_id_from_link(link)
        
        if chat_id:
            print(f"\n💡 COPY THIS ID: {chat_id}")
            print("\n" + "=" * 50 + "\n")
        else:
            print("\n❌ Failed to get ID. Try again.\n")

if __name__ == "__main__":
    asyncio.run(main())