from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Bot
from database import get_session, Post, PostSchedule, PostChannel, ScheduledJob
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)
scheduler = None

def start_scheduler(application):
    global scheduler
    if scheduler is None:
        scheduler = AsyncIOScheduler()
        scheduler.start()
        schedule_all_posts(application.bot)
        logger.info("Scheduler iniciado")

def schedule_all_posts(bot):
    session = get_session()
    try:
        posts = session.query(Post).filter_by(is_active=True).all()
        for post in posts:
            schedule = session.query(PostSchedule).filter_by(post_id=post.id, is_enabled=True).first()
            if schedule:
                schedule_post(bot, post, schedule)
    finally:
        session.close()

def schedule_post(bot: Bot, post: Post, schedule: PostSchedule):
    remove_post_jobs(post.id)
    
    days = [int(d) for d in schedule.days_of_week.split(',')]
    hour, minute = map(int, schedule.send_time.split(':'))
    
    # APScheduler usa 0-6 para Lun-Dom, nuestra DB usa 1-7
    aps_days = ','.join(str(d - 1) for d in days)
    
    try:
        scheduler.add_job(
            send_post_to_channels,
            trigger=CronTrigger(
                day_of_week=aps_days,
                hour=hour,
                minute=minute
            ),
            args=[bot, post.id],
            id=f"send_{post.id}",
            replace_existing=True
        )
        logger.info(f"Programado post {post.id} para {schedule.send_time} días {aps_days}")
    except Exception as e:
        logger.error(f"Error programando post {post.id}: {e}")

async def send_post_to_channels(bot: Bot, post_id: int):
    session = get_session()
    try:
        post = session.query(Post).filter_by(id=post_id, is_active=True).first()
        if not post:
            return
        
        post_channels = session.query(PostChannel).filter_by(post_id=post_id).all()
        channels = [pc.channel_id for pc in post_channels]
        
        if not channels:
            logger.warning(f"No hay canales para post {post_id}")
            return
        
        schedule = session.query(PostSchedule).filter_by(post_id=post_id, is_enabled=True).first()
        if not schedule:
            return
        
        for channel_id in channels:
            try:
                message = None
                
                # Intentar reenviar mensaje original si está configurado
                if schedule.forward_original and post.source_channel and post.source_message_id:
                    try:
                        message = await bot.forward_message(
                            chat_id=channel_id,
                            from_chat_id=post.source_channel,
                            message_id=post.source_message_id
                        )
                        logger.info(f"Reenviado mensaje original a {channel_id}")
                    except Exception:
                        logger.info(f"No se pudo reenviar, enviando contenido guardado")
                
                # Si no se pudo reenviar, enviar contenido guardado
                if not message:
                    message = await send_content_by_type(bot, channel_id, post)
                
                if message:
                    # Fijar mensaje si está configurado
                    if schedule.pin_message:
                        try:
                            await bot.pin_chat_message(
                                chat_id=channel_id,
                                message_id=message.message_id,
                                disable_notification=True
                            )
                        except Exception as pin_error:
                            logger.warning(f"No se pudo fijar mensaje: {pin_error}")
                    
                    # Programar eliminación
                    if schedule.delete_after_hours > 0:
                        delete_time = datetime.utcnow() + timedelta(hours=schedule.delete_after_hours)
                        scheduler.add_job(
                            delete_message,
                            trigger='date',
                            run_date=delete_time,
                            args=[bot, channel_id, message.message_id],
                            id=f"delete_{post.id}_{channel_id}_{message.message_id}",
                            replace_existing=True
                        )
                
                logger.info(f"Enviado post {post_id} a canal {channel_id}")
                
            except Exception as e:
                logger.error(f"Error enviando post {post_id} a {channel_id}: {e}")
    
    finally:
        session.close()

async def send_content_by_type(bot: Bot, channel_id: str, post: Post):
    """Envía contenido según el tipo"""
    try:
        if post.content_type == 'text':
            return await bot.send_message(
                chat_id=channel_id,
                text=post.content_text
            )
        elif post.content_type == 'photo':
            return await bot.send_photo(
                chat_id=channel_id,
                photo=post.file_id,
                caption=post.content_text
            )
        elif post.content_type == 'video':
            return await bot.send_video(
                chat_id=channel_id,
                video=post.file_id,
                caption=post.content_text
            )
        elif post.content_type == 'audio':
            return await bot.send_audio(
                chat_id=channel_id,
                audio=post.file_id,
                caption=post.content_text
            )
        elif post.content_type == 'document':
            return await bot.send_document(
                chat_id=channel_id,
                document=post.file_id,
                caption=post.content_text
            )
        elif post.content_type == 'animation':
            return await bot.send_animation(
                chat_id=channel_id,
                animation=post.file_id,
                caption=post.content_text
            )
        elif post.content_type == 'sticker':
            return await bot.send_sticker(
                chat_id=channel_id,
                sticker=post.file_id
            )
        elif post.content_type == 'voice':
            return await bot.send_voice(
                chat_id=channel_id,
                voice=post.file_id,
                caption=post.content_text
            )
    except Exception as e:
        logger.error(f"Error enviando contenido tipo {post.content_type}: {e}")
        return None

async def delete_message(bot: Bot, channel_id: str, message_id: int):
    try:
        await bot.delete_message(chat_id=channel_id, message_id=message_id)
        logger.info(f"Eliminado mensaje {message_id} de {channel_id}")
    except Exception as e:
        logger.error(f"Error eliminando mensaje {message_id}: {e}")

def schedule_message_deletion(bot: Bot, channel_id: str, message_id: int, hours: int):
    """Programar eliminación de mensaje específico"""
    delete_time = datetime.utcnow() + timedelta(hours=hours)
    scheduler.add_job(
        delete_message,
        trigger='date',
        run_date=delete_time,
        args=[bot, channel_id, message_id],
        id=f"delete_manual_{channel_id}_{message_id}",
        replace_existing=True
    )

def reschedule_post_job(bot: Bot, post_id: int):
    session = get_session()
    try:
        post = session.query(Post).filter_by(id=post_id, is_active=True).first()
        schedule = session.query(PostSchedule).filter_by(post_id=post_id, is_enabled=True).first()
        
        if post and schedule:
            schedule_post(bot, post, schedule)
            logger.info(f"Reprogramado post {post_id}")
    finally:
        session.close()

def remove_post_jobs(post_id: int):
    send_job_id = f"send_{post_id}"
    if scheduler.get_job(send_job_id):
        scheduler.remove_job(send_job_id)
        logger.info(f"Eliminado trabajo {send_job_id}")

def stop_scheduler():
    if scheduler:
        scheduler.shutdown()
        logger.info("Scheduler detenido")
    
