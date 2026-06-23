from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from bot.core.db import get_user_settings, update_user_settings
from bot.core.state import user_states

def register_settings_handlers(app: Client):
    
    @app.on_callback_query(filters.regex("^settings$"))
    async def settings_callback(client: Client, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        settings = await get_user_settings(user_id)
        
        text = "⚙️ Settings\n━━━━━━━━━━━━━━━━━━━━\n"
        text += f"{'✅' if settings['strip_links'] else '☐'} Strip links from captions\n"
        text += f"{'✅' if settings['strip_mentions'] else '☐'} Strip @mentions\n"
        text += f"{'✅' if settings['media_only'] else '☐'} Media only (skip text msgs)\n"
        text += f"{'✅' if settings['text_only'] else '☐'} Text only (skip media msgs)\n"
        text += f"{'✅' if settings['auto_resume'] else '☐'} Auto-resume on bot restart\n"
        text += f"⏱️ Default delay: {settings['default_delay']}s\n"
        text += f"🔄 Max retries: {settings['max_retries']}"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{'✅' if settings['strip_links'] else '☐'} Strip Links", callback_data="toggle_strip_links")],
            [InlineKeyboardButton(f"{'✅' if settings['strip_mentions'] else '☐'} Strip @mentions", callback_data="toggle_strip_mentions")],
            [InlineKeyboardButton(f"{'✅' if settings['media_only'] else '☐'} Media Only", callback_data="toggle_media_only")],
            [InlineKeyboardButton(f"{'✅' if settings['text_only'] else '☐'} Text Only", callback_data="toggle_text_only")],
            [InlineKeyboardButton(f"{'✅' if settings['auto_resume'] else '☐'} Auto-resume", callback_data="toggle_auto_resume")],
            [InlineKeyboardButton(f"✏️ Default Delay: {settings['default_delay']}s", callback_data="edit_default_delay")],
            [InlineKeyboardButton(f"🔄 Max Retries: {settings['max_retries']}", callback_data="edit_max_retries")],
            [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
        ])
        
        await callback_query.message.edit_text(text, reply_markup=keyboard)
        await callback_query.answer()
    
    @app.on_callback_query(filters.regex("^toggle_"))
    async def toggle_setting_callback(client: Client, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        setting = callback_query.data.split("_")[1]
        
        settings = await get_user_settings(user_id)
        
        mapping = {
            "strip_links": "strip_links",
            "strip_mentions": "strip_mentions",
            "media_only": "media_only",
            "text_only": "text_only",
            "auto_resume": "auto_resume"
        }
        
        if setting in mapping:
            settings[mapping[setting]] = not settings[mapping[setting]]
            await update_user_settings(user_id, settings)
        
        await settings_callback(client, callback_query)
    
    @app.on_callback_query(filters.regex("^edit_default_delay$"))
    async def edit_default_delay_callback(client: Client, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        user_states.set_state(user_id, "waiting_settings_delay")
        
        await callback_query.message.edit_text(
            "✏️ Enter new default delay in seconds:\n\n"
            "💡 Examples:\n"
            "• 0.5  → fast\n"
            "• 1.0  → balanced\n"
            "• 3.0  → very safe\n\n"
            "👉 Type a number like 0.8 or 1.5:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Cancel", callback_data="settings")]
            ])
        )
        await callback_query.answer()
    
    @app.on_callback_query(filters.regex("^edit_max_retries$"))
    async def edit_max_retries_callback(client: Client, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("1", callback_data="set_retries_1"),
             InlineKeyboardButton("3", callback_data="set_retries_3"),
             InlineKeyboardButton("5", callback_data="set_retries_5")],
            [InlineKeyboardButton("10", callback_data="set_retries_10")],
            [InlineKeyboardButton("🔙 Back", callback_data="settings")]
        ])
        
        await callback_query.message.edit_text(
            "Select maximum number of retries per message:",
            reply_markup=keyboard
        )
        await callback_query.answer()
    
    @app.on_callback_query(filters.regex(r"^set_retries_(\d+)$"))
    async def set_retries_callback(client: Client, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        retries = int(callback_query.data.split("_")[2])
        
        settings = await get_user_settings(user_id)
        settings['max_retries'] = retries
        await update_user_settings(user_id, settings)
        
        await callback_query.answer(f"Max retries set to {retries}!")
        await settings_callback(client, callback_query)