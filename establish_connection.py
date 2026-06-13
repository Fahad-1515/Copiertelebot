import asyncio
from pyrogram import Client

# YOUR EXACT CREDENTIALS (from your script)
API_ID = 19059105
API_HASH = "2d429e47f268938da672c5e33348ef51"
BOT_TOKEN = "8727581309:AAFPNDInOIpm8Egxo0HTTLxCijwWUdCQRxw"
GROUP_ID = -1003944769934  # The ID your script found

async def establish_connection():
    """One-time script to connect bot to the group"""
    
    app = Client("connection", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
    
    await app.start()
    
    bot_info = await app.get_me()
    print(f"🤖 Bot: @{bot_info.username}")
    print(f"📤 Connecting to group ID: {GROUP_ID}")
    
    try:
        # Try to get group info first
        group = await app.get_chat(GROUP_ID)
        print(f"✅ Found group: {group.title}")
        
        # Send the first message (this is what establishes the connection)
        await app.send_message(GROUP_ID, "✅ Bot is now active! Will send forward logs here.")
        print("✅ Connection established! Test message sent.")
        print("\n🎉 Your bot can now send messages to this group.")
        print("You can now restart your main bot normally.")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nTroubleshooting:")
        print("1. Is @Copiertelebot an ADMIN in the group?")
        print("2. Is the bot still in the group?")
        print("3. Try removing and re-adding the bot as admin")
        
    await app.stop()

if __name__ == "__main__":
    asyncio.run(establish_connection())
    