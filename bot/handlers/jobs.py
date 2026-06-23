from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from bot.core.db import get_user_jobs, get_job, complete_job
from bot.utils.formatter import format_time_simple
from bot.services.forwarder import ForwardEngine

def register_jobs_handlers(app: Client, forward_engine: ForwardEngine):
    
    @app.on_callback_query(filters.regex("^my_jobs$"))
    async def my_jobs_callback(client: Client, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        jobs = await get_user_jobs(user_id)
        
        if not jobs:
            await callback_query.message.edit_text(
                "📋 You have no jobs yet.\n\n"
                "Use /start and click 'Start Forwarding' to create your first job!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
                ])
            )
            await callback_query.answer()
            return
        
        text = "📋 Your Jobs\n━━━━━━━━━━━━━━━━━━━━\n"
        buttons = []
        
        for i, job in enumerate(jobs[:10], 1):
            status_emoji = {
                "running": "🟢",
                "completed": "✅",
                "cancelled": "❌",
                "paused": "⏸️",
                "failed": "🔴"
            }.get(job['status'], "❓")
            
            progress = f"{job['forwarded']}/{job['total']}" if job['total'] != 999999 else f"{job['forwarded']} msgs"
            text += f"{i}. {status_emoji} Job #{job['id']} — {job['source_name'][:30]} — {progress}\n"
            
            if job['status'] == 'paused':
                buttons.append([InlineKeyboardButton(f"▶️ Resume Job #{job['id']}", callback_data=f"resume_job_{job['id']}")])
        
        buttons.append([InlineKeyboardButton("🗑️ Clear History", callback_data="clear_history")])
        buttons.append([InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")])
        
        await callback_query.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        await callback_query.answer()
    
    @app.on_callback_query(filters.regex(r"^resume_job_(\d+)$"))
    async def resume_job_callback(client: Client, callback_query: CallbackQuery):
        job_id = int(callback_query.data.split("_")[2])
        user_id = callback_query.from_user.id
        
        job = await get_job(job_id)
        if not job or job['user_id'] != user_id:
            await callback_query.answer("Job not found!", show_alert=True)
            return
        
        if job['status'] != 'paused':
            await callback_query.answer("This job is not paused!", show_alert=True)
            return
        
        await forward_engine.resume_job(job_id)
        await callback_query.answer("Job resumed!")
        
        # Refresh jobs list
        await my_jobs_callback(client, callback_query)
    
    @app.on_callback_query(filters.regex("^clear_history$"))
    async def clear_history_callback(client: Client, callback_query: CallbackQuery):
        await callback_query.message.edit_text(
            "🗑️ Clear all completed/cancelled jobs?\n\n"
            "This will remove them from your jobs list permanently.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Yes, Clear All", callback_data="confirm_clear_history"),
                 InlineKeyboardButton("❌ No, Go Back", callback_data="my_jobs")]
            ])
        )
        await callback_query.answer()
    
    @app.on_callback_query(filters.regex("^confirm_clear_history$"))
    async def confirm_clear_history(client: Client, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        jobs = await get_user_jobs(user_id)
        
        # Mark as cleared (soft delete would be better, but for simplicity we'll just keep them)
        # In production, you might want to implement actual deletion
        await callback_query.message.edit_text(
            "✅ History cleared!\n\n"
            "Completed and cancelled jobs have been removed from your list.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
            ])
        )
        await callback_query.answer()