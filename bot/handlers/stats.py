from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from bot.core.db import get_user_stats

def register_stats_handlers(app: Client):
    
    @app.on_callback_query(filters.regex("^stats$"))
    async def stats_callback(client: Client, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        stats = await get_user_stats(user_id)
        
        text = f"""📊 Your Stats
━━━━━━━━━━━━━━━━━━━━
📨 Total Forwarded:  {stats['total_forwarded']:,} messages
✅ Completed Jobs:   {stats['completed']}
❌ Cancelled Jobs:   {stats['cancelled']}
⏸️ Paused Jobs:      {stats['paused']}
⏱️ Avg Delay Used:   {stats['avg_delay']:.1f}s
━━━━━━━━━━━━━━━━━━━━
[🏠 Main Menu]"""
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ])
        
        await callback_query.message.edit_text(text, reply_markup=keyboard)
        await callback_query.answer()