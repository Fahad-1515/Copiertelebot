from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from bot.core.db import get_user_settings, update_user_settings

def register_settings_handlers(app: Client):
    
    @app.on_callback_query(filters.regex("^settings$"))
    async def settings_callback(client: Client, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        settings = await get_user_settings(user_id)
        
        delay_display = f"{settings['default_delay']}s"
        retry_display = "ON ✅" if settings['retry_enabled'] else "OFF ❌"
        mode_display = "Copy ✅" if settings['forward_mode'] == 'copy' else "Forward with tag"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"⏱️ Default Delay: {delay_display}", callback_data="edit_delay"),
             InlineKeyboardButton(f"🔁 Retry: {retry_display}", callback_data="toggle_retry")],
            [InlineKeyboardButton(f"📋 Forward Mode: {mode_display}", callback_data="toggle_mode"),
             InlineKeyboardButton(f"🔢 Max Retries: {settings['max_retries']}", callback_data="edit_retries")],
            [InlineKeyboardButton("💾 Save Changes", callback_data="save_settings"),
             InlineKeyboardButton("↩️ Back to Menu", callback_data="main_menu")]
        ])
        
        await callback_query.message.edit_text(
            "⚙️ Settings\n━━━━━━━━━━━━━━━━━━━━\n"
            "Configure your default preferences here.\n"
            "These settings apply to all your forwarding jobs.\n━━━━━━━━━━━━━━━━━━━━",
            reply_markup=keyboard
        )
        await callback_query.answer()
    
    @app.on_callback_query(filters.regex("^edit_delay$"))
    async def edit_delay_callback(client: Client, callback_query: CallbackQuery):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("0.5s", callback_data="set_delay_0.5"),
             InlineKeyboardButton("1s", callback_data="set_delay_1"),
             InlineKeyboardButton("2s", callback_data="set_delay_2")],
            [InlineKeyboardButton("3s", callback_data="set_delay_3"),
             InlineKeyboardButton("✏️ Custom", callback_data="set_delay_custom")],
            [InlineKeyboardButton("↩️ Back to Settings", callback_data="settings")]
        ])
        
        await callback_query.message.edit_text(
            "Select default delay for new jobs:",
            reply_markup=keyboard
        )
        await callback_query.answer()
    
    @app.on_callback_query(filters.regex(r"^set_delay_(\d+\.?\d*|custom)$"))
    async def set_delay_callback(client: Client, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        value = callback_query.data.split("_")[2]
        
        if value == "custom":
            await callback_query.message.edit_text(
                "✏️ Enter custom delay in seconds (e.g., 0.8, 1.5, 3):\n\n"
                "Type a number between 0.3 and 60:"
            )
            # Store that we're waiting for custom delay input
            await callback_query.answer()
            # This would need state management, but for simplicity we'll skip
            return
        
        delay = float(value)
        settings = await get_user_settings(user_id)
        settings['default_delay'] = delay
        await update_user_settings(user_id, settings)
        
        await callback_query.answer(f"Delay set to {delay}s!")
        await settings_callback(client, callback_query)
    
    @app.on_callback_query(filters.regex("^toggle_retry$"))
    async def toggle_retry_callback(client: Client, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        settings = await get_user_settings(user_id)
        settings['retry_enabled'] = not settings['retry_enabled']
        await update_user_settings(user_id, settings)
        
        await callback_query.answer(f"Retry {'enabled' if settings['retry_enabled'] else 'disabled'}!")
        await settings_callback(client, callback_query)
    
    @app.on_callback_query(filters.regex("^toggle_mode$"))
    async def toggle_mode_callback(client: Client, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        settings = await get_user_settings(user_id)
        settings['forward_mode'] = 'tag' if settings['forward_mode'] == 'copy' else 'copy'
        await update_user_settings(user_id, settings)
        
        mode_display = "Copy" if settings['forward_mode'] == 'copy' else "Forward with tag"
        await callback_query.answer(f"Mode set to {mode_display}!")
        await settings_callback(client, callback_query)
    
    @app.on_callback_query(filters.regex("^edit_retries$"))
    async def edit_retries_callback(client: Client, callback_query: CallbackQuery):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("1", callback_data="set_retries_1"),
             InlineKeyboardButton("3", callback_data="set_retries_3"),
             InlineKeyboardButton("5", callback_data="set_retries_5")],
            [InlineKeyboardButton("✏️ Custom", callback_data="set_retries_custom")],
            [InlineKeyboardButton("↩️ Back to Settings", callback_data="settings")]
        ])
        
        await callback_query.message.edit_text(
            "Select maximum number of retries per message:",
            reply_markup=keyboard
        )
        await callback_query.answer()
    
    @app.on_callback_query(filters.regex(r"^set_retries_(\d+|custom)$"))
    async def set_retries_callback(client: Client, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        value = callback_query.data.split("_")[2]
        
        if value == "custom":
            await callback_query.message.edit_text(
                "✏️ Enter custom retry count (1-10):\n\n"
                "Type a number:"
            )
            await callback_query.answer()
            return
        
        retries = int(value)
        settings = await get_user_settings(user_id)
        settings['max_retries'] = retries
        await update_user_settings(user_id, settings)
        
        await callback_query.answer(f"Max retries set to {retries}!")
        await settings_callback(client, callback_query)
    
    @app.on_callback_query(filters.regex("^save_settings$"))
    async def save_settings_callback(client: Client, callback_query: CallbackQuery):
        await callback_query.answer("Settings saved!")
        await settings_callback(client, callback_query)