import asyncio
import logging
from aiohttp import web
from pyrogram import Client, idle
from bot.core.config import Config
from bot.core.db import init_db
from bot.handlers import register_handlers

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def keep_alive_server():
    """Keep Render service alive"""
    app = web.Application()
    async def health_check(request):
        return web.Response(text="Bot is running")
    app.router.add_get('/', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 10000)
    await site.start()
    logger.info("Keep-alive server started on port 10000")

async def main():
    await init_db()
    
    app = Client(
        "forward_bot",
        api_id=Config.API_ID,
        api_hash=Config.API_HASH,
        bot_token=Config.BOT_TOKEN
    )
    
    await app.start()
    logger.info("Bot started!")
    
    register_handlers(app)
    
    asyncio.create_task(keep_alive_server())
    
    await idle()
    await app.stop()

if __name__ == "__main__":
    asyncio.run(main())