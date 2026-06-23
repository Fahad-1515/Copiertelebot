from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from bot.core.db import add_user, get_user_settings
from bot.utils.formatter import format_main_menu
from bot.services.logger import AdminLogger

def register_start_handlers(app: Client, admin_logger: AdminLogger):
    
    @app.on_message(filters.command("start") & filters.private)
    async def start_command(client: Client, message: Message):
        user = message.from_user
        await add_user(user.id, user.username or "", user.first_name or "")
        
        # Notify admin about new user
        await admin_logger.send_new_user_notification(
            user.id, user.username or "", user.first_name or ""
        )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("▶️ Start Forwarding", callback_data="new_job")],
            [InlineKeyboardButton("📋 My Jobs", callback_data="my_jobs"),
             InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
            [InlineKeyboardButton("❓ Help", callback_data="help"),
             InlineKeyboardButton("📊 Stats", callback_data="stats")]
        ])
        
        await message.reply(
            format_main_menu(),
            reply_markup=keyboard
        )
    
    @app.on_callback_query(filters.regex("^main_menu$"))
    async def main_menu_callback(client: Client, callback_query):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("▶️ Start Forwarding", callback_data="new_job")],
            [InlineKeyboardButton("📋 My Jobs", callback_data="my_jobs"),
             InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
            [InlineKeyboardButton("❓ Help", callback_data="help"),
             InlineKeyboardButton("📊 Stats", callback_data="stats")]
        ])
        
        await callback_query.message.edit_text(
            format_main_menu(),
            reply_markup=keyboard
        )
        await callback_query.answer()
    
    @app.on_callback_query(filters.regex("^help$"))
    async def help_callback(client: Client, callback_query):
        help_text = """❓ Help Center
━━━━━━━━━━━━━━━━━━━━

📌 How to use this bot:

1️⃣ Click "Start Forwarding" to begin
2️⃣ Send source channel link
3️⃣ Add destination channels
4️⃣ Choose message count
5️⃣ Set delay between messages
6️⃣ Select message filter
7️⃣ Confirm and start

💡 Tips:
• Bot must be admin in destination channels
• Lower delay = faster but may hit rate limits
• Use 1-2 seconds delay for large jobs
• You can pause/resume jobs anytime

🔗 Supported formats:
• https://t.me/channel
• @channel
• -1001234567890

[🏠 Main Menu]"""
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ])
        
        await callback_query.message.edit_text(
            help_text,
            reply_markup=keyboard
        )
        await callback_query.answer()