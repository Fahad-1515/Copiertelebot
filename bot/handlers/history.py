from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from bot.core.db import get_history
from bot.utils.formatter import format_time_simple

def register_history_handlers(app: Client):
    
    @app.on_callback_query(filters.regex("^history$"))
    async def history_callback(client: Client, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        history = await get_history(user_id, 10)
        
        if not history:
            text = "📜 Job History\n━━━━━━━━━━━━━━━━━━━━\nNo completed jobs yet."
        else:
            text = "📜 Job History\n━━━━━━━━━━━━━━━━━━━━\n"
            for job in history:
                status_emoji = "✅" if job['status'] == 'completed' else "🛑"
                time_str = ""
                if job['completed_at']:
                    time_str = job['completed_at'][:10]
                text += f"{status_emoji} {time_str} {job['source_name'][:30]}\n"
                text += f"   {job['forwarded']} msgs | {job['errors']} errors\n"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
        ])
        
        await callback_query.message.edit_text(text, reply_markup=keyboard)
        await callback_query.answer()