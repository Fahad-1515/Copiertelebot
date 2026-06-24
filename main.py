import asyncio
import logging
import os
import json
import sys
from aiohttp import web
from pyrogram import Client, idle
from bot.core.config import Config
from bot.core.db import init_db, get_job, update_job_progress, complete_job
from bot.handlers import register_handlers
from bot.services.forwarder import ForwardEngine

# CRITICAL FIX: Set up event loop policy for Python 3.14+
if sys.version_info >= (3, 14):
    import asyncio
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except:
        pass

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def load_incomplete_jobs():
    """Load incomplete jobs from progress files on startup"""
    progress_dir = "progress"
    if not os.path.exists(progress_dir):
        os.makedirs(progress_dir)
        return {}
    
    jobs = {}
    for filename in os.listdir(progress_dir):
        if filename.endswith(".json"):
            try:
                job_id = int(filename.replace(".json", ""))
                with open(os.path.join(progress_dir, filename), "r") as f:
                    data = json.load(f)
                    jobs[job_id] = data
                logger.info(f"Loaded progress for job {job_id}: {data.get('forwarded', 0)} messages")
            except Exception as e:
                logger.warning(f"Failed to load progress for {filename}: {e}")
    return jobs

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
    
    # Load incomplete jobs
    incomplete_jobs = await load_incomplete_jobs()
    
    # Initialize forward engine with loaded jobs
    forward_engine = ForwardEngine(app, incomplete_jobs)
    
    # Register handlers
    register_handlers(app, forward_engine)
    
    # ============================================================
    # Initialize Admin Logger and send initial dashboard
    # ============================================================
    from bot.services.logger import AdminLogger
    admin_logger = AdminLogger(app)
    await admin_logger.init_bot_info()
    await admin_logger.update_live_dashboard()
    logger.info("✅ Admin dashboard initialized!")
    
    asyncio.create_task(keep_alive_server())
    
    await idle()
    await app.stop()

if __name__ == "__main__":
    # CRITICAL FIX: Ensure event loop exists before running
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    asyncio.run(main())
