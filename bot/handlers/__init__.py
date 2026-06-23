from pyrogram import Client
from bot.services.logger import AdminLogger
from bot.services.forwarder import ForwardEngine
from bot.handlers.start import register_start_handlers
from bot.handlers.forwarding import register_forwarding_handlers
from bot.handlers.jobs import register_jobs_handlers
from bot.handlers.settings import register_settings_handlers
from bot.handlers.stats import register_stats_handlers

def register_handlers(app: Client):
    admin_logger = AdminLogger(app)
    forward_engine = ForwardEngine(app, admin_logger)
    
    register_start_handlers(app, admin_logger)
    register_forwarding_handlers(app, forward_engine)
    register_jobs_handlers(app, forward_engine)
    register_settings_handlers(app)
    register_stats_handlers(app)