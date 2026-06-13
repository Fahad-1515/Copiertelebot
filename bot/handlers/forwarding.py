import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from bot.core.db import create_job, get_user_settings, update_job_progress
from bot.core.state import user_states
from bot.utils.link_parser import parse_chat_link, get_chat_info, parse_destination
from bot.utils.formatter import format_source_confirmation, format_destinations_list, format_final_confirmation
from bot.utils.progress import format_time
from bot.services.forwarder import ForwardEngine

def register_forwarding_handlers(app: Client, forward_engine: ForwardEngine):
    
    @app.on_callback_query(filters.regex("^new_job$"))
    async def new_job_callback(client: Client, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        user_states.set_state(user_id, "waiting_source")
        user_states.set_data(user_id, "destinations", [])
        
        await callback_query.message.edit_text(
            """📥 Send me the source channel link or username.

💡 Examples you can send:
- https://t.me/examplechannel
- https://t.me/c/1234567890/5
- @examplechannel
- -1001234567890

👉 Just copy any channel link and paste it here!

[❌ Cancel]""",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel_setup")]
            ])
        )
        await callback_query.answer()
    
    @app.on_message(filters.private & filters.text)
    async def handle_wizard_input(client: Client, message: Message):
        user_id = message.from_user.id
        state = user_states.get_state(user_id)
        
        if not state:
            return
        
        text = message.text.strip()
        
        if state == "waiting_source":
            chat_id = await parse_chat_link(text)
            if not chat_id:
                await message.reply(
                    "❌ Invalid link format!\n\n"
                    "Please send a valid channel link like:\n"
                    "• https://t.me/channelname\n"
                    "• @channelname\n"
                    "• -1001234567890"
                )
                return
            
            name, members = await get_chat_info(client, chat_id)
            if not name:
                await message.reply(
                    "❌ Cannot access this channel!\n\n"
                    "Make sure:\n"
                    "• The channel exists\n"
                    "• The channel is public or bot is member"
                )
                return
            
            user_states.set_data(user_id, "source_id", chat_id)
            user_states.set_data(user_id, "source_name", name)
            user_states.set_data(user_id, "source_members", members)
            user_states.set_state(user_id, "confirming_source")
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Confirm", callback_data="confirm_source"),
                 InlineKeyboardButton("🔄 Change Source", callback_data="change_source")]
            ])
            
            await message.reply(
                format_source_confirmation(name, chat_id, members),
                reply_markup=keyboard
            )
        
        elif state == "waiting_destination":
            if text.lower() == '/done':
                destinations = user_states.get_data(user_id, "destinations") or []
                if not destinations:
                    await message.reply("❌ Please add at least one destination before using /done")
                    return
                
                user_states.set_state(user_id, "confirming_destinations")
                
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Confirm", callback_data="confirm_destinations"),
                     InlineKeyboardButton("➕ Add More", callback_data="add_more_destinations"),
                     InlineKeyboardButton("❌ Remove One", callback_data="remove_destination")]
                ])
                
                await message.reply(
                    format_destinations_list(destinations),
                    reply_markup=keyboard
                )
                return
            
            dest_id = await parse_destination(text)
            if not dest_id:
                await message.reply(
                    "❌ Invalid destination format!\n\n"
                    "Please send a valid channel link:\n"
                    "• https://t.me/channel\n"
                    "• @channel\n"
                    "• -1001234567890\n\n"
                    "Type /done when finished."
                )
                return
            
            try:
                chat = await client.get_chat(dest_id)
                name = chat.title or chat.first_name
                
                destinations = user_states.get_data(user_id, "destinations") or []
                destinations.append({"id": dest_id, "name": name})
                user_states.set_data(user_id, "destinations", destinations)
                
                await message.reply(
                    f"✅ Added: {name} ({len(destinations)} saved) — send more or /done"
                )
            except Exception as e:
                await message.reply(
                    f"❌ Cannot access {dest_id}!\n"
                    f"Error: {str(e)[:100]}"
                )
        
        elif state == "waiting_message_count":
            if text.lower() == 'all':
                count = 999999
            else:
                try:
                    count = int(text)
                    if count <= 0 or count > 10000:
                        raise ValueError
                except:
                    await message.reply("❌ Please send a valid number (1-10000) or 'all'")
                    return
            
            user_states.set_data(user_id, "message_count", count)
            user_states.set_state(user_id, "waiting_delay")
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("0.5s", callback_data="delay_0.5"),
                 InlineKeyboardButton("1s", callback_data="delay_1"),
                 InlineKeyboardButton("2s", callback_data="delay_2")],
                [InlineKeyboardButton("3s", callback_data="delay_3"),
                 InlineKeyboardButton("✏️ Custom", callback_data="delay_custom")]
            ])
            
            await message.reply(
                """⏱️ Set delay between messages:
━━━━━━━━━━━━━━━━━━━━
💡 Lower = faster but may hit rate limits
   Higher = slower but safer

Recommended: 1s for large jobs (1000+ msgs)
             0.5s for small jobs (under 200)
━━━━━━━━━━━━━━━━━━━━
Select delay:""",
                reply_markup=keyboard
            )
        
        elif state == "waiting_custom_delay":
            try:
                delay = float(text)
                if delay < 0.3 or delay > 60:
                    raise ValueError
                user_states.set_data(user_id, "delay", delay)
                user_states.set_state(user_id, "waiting_filter")
                
                await proceed_to_filter(message, user_id)
            except:
                await message.reply("❌ Please send a valid number between 0.3 and 60 (e.g., 0.8, 1.5, 3)")
    
    @app.on_callback_query()
    async def handle_forwarding_callbacks(client: Client, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        data = callback_query.data
        
        if data == "confirm_source":
            user_states.set_state(user_id, "waiting_destination")
            await callback_query.message.edit_text(
                """📤 Send destination channel(s) one by one.
Type /done when finished.

💡 Examples you can send:
- @mychannel
- https://t.me/mychannel
- -1009876543210

👉 Send the first destination now:"""
            )
            await callback_query.answer()
        
        elif data == "change_source":
            user_states.set_state(user_id, "waiting_source")
            await callback_query.message.edit_text(
                "📥 Send me the new source channel link:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("❌ Cancel", callback_data="cancel_setup")]
                ])
            )
            await callback_query.answer()
        
        elif data == "confirm_destinations":
            user_states.set_state(user_id, "waiting_message_count")
            await callback_query.message.edit_text(
                """📩 How many messages to forward?

💡 Examples:
- 50   → forwards last 50 messages
- 200  → forwards last 200 messages
- all  → forwards entire channel history

👉 Send a number or type 'all':"""
            )
            await callback_query.answer()
        
        elif data == "add_more_destinations":
            user_states.set_state(user_id, "waiting_destination")
            await callback_query.message.edit_text(
                "➕ Send more destination channels (type /done when finished):"
            )
            await callback_query.answer()
        
        elif data == "remove_destination":
            destinations = user_states.get_data(user_id, "destinations") or []
            if not destinations:
                await callback_query.answer("No destinations to remove!")
                return
            
            keyboard_buttons = []
            for i, dest in enumerate(destinations):
                keyboard_buttons.append(
                    [InlineKeyboardButton(f"❌ {dest['name'][:30]}", callback_data=f"remove_dest_{i}")]
                )
            keyboard_buttons.append([InlineKeyboardButton("↩️ Back", callback_data="back_to_destinations")])
            
            await callback_query.message.edit_text(
                "Select destination to remove:",
                reply_markup=InlineKeyboardMarkup(keyboard_buttons)
            )
            await callback_query.answer()
        
        elif data.startswith("remove_dest_"):
            index = int(data.split("_")[2])
            destinations = user_states.get_data(user_id, "destinations") or []
            if 0 <= index < len(destinations):
                removed = destinations.pop(index)
                user_states.set_data(user_id, "destinations", destinations)
                
                await callback_query.answer(f"Removed {removed['name']}")
                
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Confirm", callback_data="confirm_destinations"),
                     InlineKeyboardButton("➕ Add More", callback_data="add_more_destinations"),
                     InlineKeyboardButton("❌ Remove One", callback_data="remove_destination")]
                ])
                
                await callback_query.message.edit_text(
                    format_destinations_list(destinations),
                    reply_markup=keyboard
                )
        
        elif data == "back_to_destinations":
            destinations = user_states.get_data(user_id, "destinations") or []
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Confirm", callback_data="confirm_destinations"),
                 InlineKeyboardButton("➕ Add More", callback_data="add_more_destinations"),
                 InlineKeyboardButton("❌ Remove One", callback_data="remove_destination")]
            ])
            
            await callback_query.message.edit_text(
                format_destinations_list(destinations),
                reply_markup=keyboard
            )
            await callback_query.answer()
        
        elif data.startswith("delay_"):
            if data == "delay_0.5":
                delay = 0.5
            elif data == "delay_1":
                delay = 1.0
            elif data == "delay_2":
                delay = 2.0
            elif data == "delay_3":
                delay = 3.0
            elif data == "delay_custom":
                user_states.set_state(user_id, "waiting_custom_delay")
                await callback_query.message.edit_text(
                    "✏️ Enter delay in seconds:\n\n"
                    "💡 Examples:\n"
                    "• 0.5  → fast (500ms between messages)\n"
                    "• 1.2  → balanced\n"
                    "• 3    → very safe, no rate limits\n\n"
                    "👉 Type a number like 0.8 or 1.5:"
                )
                await callback_query.answer()
                return
            
            user_states.set_data(user_id, "delay", delay)
            user_states.set_state(user_id, "waiting_filter")
            await proceed_to_filter(callback_query.message, user_id)
            await callback_query.answer()
        
        elif data.startswith("filter_"):
            filter_map = {
                "all": "All Messages",
                "media_only": "Media Only",
                "text_only": "Text Only",
                "photos_only": "Photos Only",
                "videos_only": "Videos Only",
                "docs_only": "Docs Only"
            }
            
            filter_type = "_".join(data.split("_")[1:])
            user_states.set_data(user_id, "filter_type", filter_type)
            
            source_name = user_states.get_data(user_id, "source_name")
            destinations = user_states.get_data(user_id, "destinations") or []
            total = user_states.get_data(user_id, "message_count")
            delay = user_states.get_data(user_id, "delay")
            
            est_time = total * delay if isinstance(total, int) else "unknown"
            if isinstance(est_time, (int, float)):
                est_time = format_time(est_time)
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("▶️ Start Now", callback_data="start_forwarding"),
                 InlineKeyboardButton("✏️ Edit Settings", callback_data="edit_settings"),
                 InlineKeyboardButton("❌ Cancel", callback_data="cancel_setup")]
            ])
            
            await callback_query.message.edit_text(
                format_final_confirmation(
                    source_name, destinations,
                    total, delay, filter_map[filter_type],
                    est_time
                ),
                reply_markup=keyboard
            )
            await callback_query.answer()
        
        elif data == "start_forwarding":
            await start_forwarding_job(client, callback_query, user_id, forward_engine)
            await callback_query.answer()
        
        elif data == "edit_settings":
            user_states.set_state(user_id, "waiting_delay")
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("0.5s", callback_data="delay_0.5"),
                 InlineKeyboardButton("1s", callback_data="delay_1"),
                 InlineKeyboardButton("2s", callback_data="delay_2")],
                [InlineKeyboardButton("3s", callback_data="delay_3"),
                 InlineKeyboardButton("✏️ Custom", callback_data="delay_custom")]
            ])
            
            await callback_query.message.edit_text(
                "✏️ Edit delay setting:",
                reply_markup=keyboard
            )
            await callback_query.answer()
        
        elif data == "cancel_setup":
            user_states.clear_state(user_id)
            await callback_query.message.edit_text(
                "❌ Setup cancelled. Send /start to begin again."
            )
            await callback_query.answer()


async def proceed_to_filter(message, user_id):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("All Messages ✅", callback_data="filter_all"),
         InlineKeyboardButton("Media Only", callback_data="filter_media_only"),
         InlineKeyboardButton("Text Only", callback_data="filter_text_only")],
        [InlineKeyboardButton("Photos Only", callback_data="filter_photos_only"),
         InlineKeyboardButton("Videos Only", callback_data="filter_videos_only"),
         InlineKeyboardButton("Docs Only", callback_data="filter_docs_only")]
    ])
    
    await message.reply(
        """🎛️ What types of messages to forward?

💡 Examples:
- All Messages  → text + photos + videos + docs + everything
- Media Only    → only photos, videos, audio, documents
- Text Only     → only text messages, no media
- Photos Only   → only photo messages
- Videos Only   → only video messages
- Docs Only     → only files and documents

👉 Choose a filter:""",
        reply_markup=keyboard
    )


async def start_forwarding_job(client, callback_query, user_id, forward_engine):
    source_id = user_states.get_data(user_id, "source_id")
    source_name = user_states.get_data(user_id, "source_name")
    destinations = user_states.get_data(user_id, "destinations") or []
    total = user_states.get_data(user_id, "message_count")
    delay = user_states.get_data(user_id, "delay")
    filter_type = user_states.get_data(user_id, "filter_type")
    
    settings = await get_user_settings(user_id)
    
    from bot.services.logger import AdminLogger
    admin_logger = AdminLogger(client)
    
    admin_msg_id = await admin_logger.send_job_start(
        user_id, callback_query.from_user.username or "",
        source_name, destinations, total, delay, filter_type
    )
    
    job_id = await create_job(
        user_id, source_id, source_name, destinations,
        total, delay, filter_type, admin_msg_id
    )
    
    job_data = {
        "user_id": user_id,
        "username": callback_query.from_user.username,
        "source_name": source_name,
        "destinations": destinations,
        "total": total,
        "delay_used": delay,
        "filter_type": filter_type,
        "started_at": None
    }
    
    task = asyncio.create_task(
        forward_engine.run_forwarding_job(
            job_id, user_id, source_id, destinations,
            total, delay, filter_type, settings,
            admin_msg_id, job_data
        )
    )
    
    forward_engine.running_jobs[job_id] = task
    user_states.clear_state(user_id)
    
    await callback_query.message.edit_text(
        f"✅ Forwarding job started!\n\n"
        f"📥 Source: {source_name}\n"
        f"📤 Destinations: {len(destinations)}\n"
        f"📩 Messages: {total}\n"
        f"⏱️ Delay: {delay}s\n\n"
        f"Progress will be shown here. You can use /myjobs to manage this job."
    )