import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from bot.core.db import get_user_jobs, get_job, complete_job, delete_job, create_job, get_user_settings
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
                "running": "🔄",
                "completed": "✅",
                "cancelled": "❌",
                "paused": "⏸️",
                "failed": "🔴"
            }.get(job['status'], "❓")
            
            progress = f"{job['forwarded']}/{job['total']}" if job['total'] != 999999 else f"{job['forwarded']} msgs"
            text += f"{i}. {status_emoji} Job #{job['id']} — {job['source_name'][:30]} — {progress}\n"
            
            if job['status'] == 'paused':
                buttons.append([InlineKeyboardButton(f"▶️ Resume Job #{job['id']}", callback_data=f"resume_job_{job['id']}")])
            elif job['status'] == 'running':
                buttons.append([InlineKeyboardButton(f"⏸️ Pause Job #{job['id']}", callback_data=f"pause_job_{job['id']}")])
                buttons.append([InlineKeyboardButton(f"🛑 Stop Job #{job['id']}", callback_data=f"stop_job_{job['id']}")])
            elif job['status'] in ['completed', 'cancelled', 'failed']:
                buttons.append([InlineKeyboardButton(f"🔁 Restart Job #{job['id']}", callback_data=f"restart_job_{job['id']}")])
                buttons.append([InlineKeyboardButton(f"🗑 Delete Job #{job['id']}", callback_data=f"delete_job_{job['id']}")])
        
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
        await my_jobs_callback(client, callback_query)
    
    @app.on_callback_query(filters.regex(r"^pause_job_(\d+)$"))
    async def pause_job_callback(client: Client, callback_query: CallbackQuery):
        job_id = int(callback_query.data.split("_")[2])
        user_id = callback_query.from_user.id
        
        job = await get_job(job_id)
        if not job or job['user_id'] != user_id:
            await callback_query.answer("Job not found!", show_alert=True)
            return
        
        if job['status'] != 'running':
            await callback_query.answer("This job is not running!", show_alert=True)
            return
        
        await forward_engine.pause_job(job_id)
        await callback_query.answer("Job paused!")
        await my_jobs_callback(client, callback_query)
    
    @app.on_callback_query(filters.regex(r"^stop_job_(\d+)$"))
    async def stop_job_callback(client: Client, callback_query: CallbackQuery):
        job_id = int(callback_query.data.split("_")[2])
        user_id = callback_query.from_user.id
        
        job = await get_job(job_id)
        if not job or job['user_id'] != user_id:
            await callback_query.answer("Job not found!", show_alert=True)
            return
        
        await forward_engine.cancel_job(job_id)
        await callback_query.answer("Job stopped!")
        await my_jobs_callback(client, callback_query)
    
    @app.on_callback_query(filters.regex(r"^restart_job_(\d+)$"))
    async def restart_job_callback(client: Client, callback_query: CallbackQuery):
        job_id = int(callback_query.data.split("_")[2])
        user_id = callback_query.from_user.id
        
        job = await get_job(job_id)
        if not job or job['user_id'] != user_id:
            await callback_query.answer("Job not found!", show_alert=True)
            return
        
        settings = await get_user_settings(user_id)
        
        from bot.services.logger import AdminLogger
        admin_logger = AdminLogger(client)
        
        admin_msg_id = await admin_logger.send_job_start(
            user_id, callback_query.from_user.username or "",
            job['source_name'], job['destinations'],
            job['total'], job['delay_used'], job['filter_type']
        )
        
        new_job_id = await create_job(
            user_id, job['source_id'], job['source_name'],
            job['destinations'], job['total'], job['delay_used'],
            job['filter_type'], admin_msg_id, job['start_msg_id']
        )
        
        job_data = {
            "user_id": user_id,
            "username": callback_query.from_user.username,
            "source_name": job['source_name'],
            "destinations": job['destinations'],
            "total": job['total'],
            "delay_used": job['delay_used'],
            "filter_type": job['filter_type'],
            "start_msg_id": job['start_msg_id']
        }
        
        task = asyncio.create_task(
            forward_engine.run_forwarding_job(
                new_job_id, user_id, job['source_id'],
                job['destinations'], job['total'], job['delay_used'],
                job['filter_type'], settings, admin_msg_id, job_data,
                job['start_msg_id']
            )
        )
        
        forward_engine.running_jobs[new_job_id] = task
        await callback_query.answer("Job restarted!")
        await my_jobs_callback(client, callback_query)
    
    @app.on_callback_query(filters.regex(r"^delete_job_(\d+)$"))
    async def delete_job_callback(client: Client, callback_query: CallbackQuery):
        job_id = int(callback_query.data.split("_")[2])
        user_id = callback_query.from_user.id
        
        await delete_job(job_id, user_id)
        await callback_query.answer("Job deleted!")
        await my_jobs_callback(client, callback_query)