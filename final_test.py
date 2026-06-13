import asyncio
from pyrogram import Client

API_ID = 19059105
API_HASH = "2d429e47f268938da672c5e33348ef51"
BOT_TOKEN = "8727581309:AAFPNDInOIpm8Egxo0HTTLxCijwWUdCQRxw"
GROUP_ID = -1003944769934

async def test():
    app = Client("final_test", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
    
    await app.start()
    
    bot = await app.get_me()
    print(f"🤖 Bot: @{bot.username}")
    print(f"📤 Sending test message to group...")
    
    try:
        # Send a simple test message
        await app.send_message(GROUP_ID, "✅ Bot is online and has admin access!")
        print("✅ SUCCESS! Test message sent to group!")
        print("\n🎉 Your bot is fully connected!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    
    await app.stop()

if __name__ == "__main__":
    asyncio.run(test())