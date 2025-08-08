from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from database import Post, PostSchedule, PostChannel, ScheduledJob
from datetime import datetime, timedelta
from config import TIMEZONE, ADMIN_ID
import logging
import pytz

logger = logging.getLogger(__name__)
scheduler = None

def start_scheduler(application):
    global scheduler
    if scheduler is None:
        # Configurar scheduler con timezone de Cuba
        cuba_tz = pytz.timezone(TIMEZONE)
        scheduler = AsyncIOScheduler(timezone=cuba_tz)
        scheduler.start()
        schedule_all_posts(application.bot)
        logger.info(f"Scheduler iniciado con timezone: {TIMEZONE}")

def schedule_all_posts(bot):
    try:
        posts = Post.find_active()
        for post in posts:
            schedule = PostSchedule.find_by_post_id(str(post._id))
            if schedule:
                schedule_post(bot, post, schedule)
    except Exception as e:
        logger.error(f"Error scheduling all posts: {e}")

def schedule_post(bot: Bot, post: Post, schedule: PostSchedule):
    remove_post_jobs(str(post._id))
    
    days = [int(d) for d in schedule.days_of_week.split(',')]
    hour, minute = map(int, schedule.send_time.split(':'))
    
    # APScheduler usa 0-6 para Lun-Dom, nuestra DB usa 1-7
    aps_days = ','.join(str(d - 1) for d in days)
    
    try:
        scheduler.add_job(
            send_post_to_channels_with_notification,
            trigger=CronTrigger(
                day_of_week=aps_days,
                hour=hour,
                minute=minute,
                timezone=TIMEZONE
            ),
            args=[bot, str(post._id), False],  # False = no es manual
            id=f"send_{str(post._id)}",
            replace_existing=True
        )
        logger.info(f"Programado post {str(post._id)} para {schedule.send_time} días {aps_days} (timezone: {TIMEZONE})")
    except Exception as e:
        logger.error(f"Error programando post {str(post._id)}: {e}")

async def send_post_to_channels_with_notification(bot: Bot, post_id: str, is_manual: bool = False):
    """Envía post a canales y notifica al administrador"""
    cuba_tz = pytz.timezone(TIMEZONE)
    send_time = datetime.now(cuba_tz)
    
    try:
        post = Post.find_by_id(post_id)
        if not post:
            logger.error(f"Post {post_id} no encontrado")
            return
        
        post_channels = PostChannel.find_by_post_id(post_id)
        channels = [pc.channel_id for pc in post_channels]
        
        if not channels:
            logger.warning(f"No hay canales para post {post_id}")
            return
        
        schedule = PostSchedule.find_by_post_id(post_id)
        if not schedule:
            logger.error(f"Horario no encontrado para post {post_id}")
            return
        
        # Estadísticas de envío
        sent_count = 0
        error_count = 0
        sent_messages = []
        failed_channels = []
        
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
                    sent_count += 1
                    sent_messages.append({
                        'channel_id': channel_id,
                        'message_id': message.message_id,
                        'post_id': post_id
                    })
                    
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
                        delete_time = send_time + timedelta(hours=schedule.delete_after_hours)
                        scheduler.add_job(
                            delete_message_with_notification,
                            trigger='date',
                            run_date=delete_time,
                            args=[bot, channel_id, message.message_id, post_id, post.name, send_time],
                            id=f"delete_{post_id}_{channel_id}_{message.message_id}",
                            replace_existing=True
                        )
                else:
                    error_count += 1
                    failed_channels.append({
                        'channel_id': channel_id,
                        'error': 'No se pudo enviar el mensaje'
                    })
                
                logger.info(f"Enviado post {post_id} a canal {channel_id}")
                
            except Exception as e:
                error_count += 1
                failed_channels.append({
                    'channel_id': channel_id,
                    'error': str(e)
                })
                logger.error(f"Error enviando post {post_id} a {channel_id}: {e}")
        
        # Enviar notificación al administrador
        await send_post_notification(
            bot, post, send_time, len(channels), sent_count, 
            error_count, failed_channels, is_manual
        )
        
        # Guardar información de mensajes enviados para eliminación posterior
        if sent_messages:
            save_sent_messages_info(post_id, sent_messages, send_time)
    
    except Exception as e:
        logger.error(f"Error in send_post_to_channels_with_notification: {e}")

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

async def send_post_notification(bot: Bot, post: Post, send_time: datetime, 
                                total_channels: int, sent_count: int, error_count: int,
                                failed_channels: list, is_manual: bool):
    """Envía notificación al administrador sobre el envío del post"""
    try:
        # Crear mensaje de notificación
        notification_text = (
            f"📤 **{'Envío Manual' if is_manual else 'Envío Automático'} Completado**\n\n"
            f"🕐 **Hora de envío:** {send_time.strftime('%H:%M:%S')}\n"
            f"📅 **Fecha:** {send_time.strftime('%d/%m/%Y')}\n"
            f"📝 **Post:** {post.name}\n"
            f"📺 **Canales totales:** {total_channels}\n"
            f"✅ **Envíos exitosos:** {sent_count}\n"
            f"❌ **Envíos fallidos:** {error_count}\n\n"
        )
        
        # Añadir razones de fallo si las hay
        if failed_channels:
            notification_text += "**Razones de fallo:**\n"
            for i, failed in enumerate(failed_channels[:5], 1):  # Mostrar solo los primeros 5
                notification_text += f"{i}. Canal `{failed['channel_id']}`: {failed['error']}\n"
            if len(failed_channels) > 5:
                notification_text += f"... y {len(failed_channels) - 5} errores más\n"
        
        # Crear botones de acción
        keyboard = [
            [InlineKeyboardButton("🔄 Reenviar", callback_data=f"resend_post_{post._id}")],
            [InlineKeyboardButton("🗑️ Eliminar de Todos", callback_data=f"delete_all_posts_{post._id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Enviar notificación y guardar el message_id para eliminar después
        notification_msg = await bot.send_message(
            chat_id=ADMIN_ID,
            text=notification_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        # Guardar el ID del mensaje de notificación para eliminarlo después
        save_notification_message_id(str(post._id), notification_msg.message_id, send_time)
        
        logger.info(f"Notificación de envío enviada para post {post._id}")
        
    except Exception as e:
        logger.error(f"Error enviando notificación de post: {e}")

async def delete_message_with_notification(bot: Bot, channel_id: str, message_id: int, 
                                         post_id: str, post_name: str, send_time: datetime):
    """Elimina mensaje y actualiza estadísticas de eliminación"""
    cuba_tz = pytz.timezone(TIMEZONE)
    delete_time = datetime.now(cuba_tz)
    
    success = False
    error_msg = None
    
    try:
        await bot.delete_message(chat_id=channel_id, message_id=message_id)
        success = True
        logger.info(f"Eliminado mensaje {message_id} de {channel_id}")
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error eliminando mensaje {message_id}: {e}")
    
    # Actualizar estadísticas globales de eliminación
    await update_deletion_stats(bot, post_id, post_name, send_time, delete_time, success, error_msg)

def save_sent_messages_info(post_id: str, sent_messages: list, send_time: datetime):
    """Guarda información de mensajes enviados para tracking de eliminación"""
    try:
        from database import db
        
        # Limpiar registros anteriores del mismo post para este envío
        db.sent_messages.delete_many({
            'post_id': post_id,
            'send_time': send_time
        })
        
        # Guardar nuevos registros
        for msg_info in sent_messages:
            db.sent_messages.insert_one({
                'post_id': post_id,
                'channel_id': msg_info['channel_id'],
                'message_id': msg_info['message_id'],
                'send_time': send_time,
                'sent_at': datetime.utcnow(),
                'deleted': False
            })
            
        logger.info(f"Guardada información de {len(sent_messages)} mensajes para post {post_id}")
        
    except Exception as e:
        logger.error(f"Error guardando info de mensajes: {e}")

def save_notification_message_id(post_id: str, notification_message_id: int, send_time: datetime):
    """Guarda el ID del mensaje de notificación para eliminarlo después"""
    try:
        from database import db
        
        db.notification_messages.insert_one({
            'post_id': post_id,
            'message_id': notification_message_id,
            'send_time': send_time,
            'deleted': False
        })
        
        logger.info(f"Guardado ID de notificación {notification_message_id} para post {post_id}")
        
    except Exception as e:
        logger.error(f"Error guardando ID de notificación: {e}")

async def update_deletion_stats(bot: Bot, post_id: str, post_name: str, send_time: datetime, 
                               delete_time: datetime, success: bool, error_msg: str = None):
    """Actualiza estadísticas de eliminación y envía notificación final"""
    try:
        from database import db
        
        # Buscar o crear registro de estadísticas de eliminación
        stats = db.deletion_stats.find_one({
            'post_id': post_id, 
            'send_time': send_time
        })
        
        if not stats:
            stats = {
                'post_id': post_id,
                'post_name': post_name,
                'send_time': send_time,
                'delete_time': delete_time,
                'total_channels': 0,
                'deleted_count': 0,
                'failed_count': 0,
                'failed_reasons': [],
                'notified': False
            }
        
        # Actualizar contadores
        stats['total_channels'] = stats.get('total_channels', 0) + 1
        
        if success:
            stats['deleted_count'] = stats.get('deleted_count', 0) + 1
            # Actualizar registro de mensaje como eliminado
            db.sent_messages.update_one(
                {
                    'post_id': post_id, 
                    'send_time': send_time,
                    'deleted': False
                },
                {'$set': {'deleted': True, 'deleted_at': datetime.utcnow()}},
            )
        else:
            stats['failed_count'] = stats.get('failed_count', 0) + 1
            if error_msg:
                if 'failed_reasons' not in stats:
                    stats['failed_reasons'] = []
                stats['failed_reasons'].append(error_msg)
        
        # Guardar estadísticas actualizadas
        db.deletion_stats.replace_one(
            {'post_id': post_id, 'send_time': send_time},
            stats,
            upsert=True
        )
        
        # Verificar si todos los mensajes han sido procesados
        pending_messages = db.sent_messages.count_documents({
            'post_id': post_id,
            'send_time': send_time,
            'deleted': False
        })
        
        # Si no hay mensajes pendientes y no se ha notificado, enviar notificación final
        if pending_messages == 0 and not stats.get('notified', False):
            # Marcar como notificado
            db.deletion_stats.update_one(
                {'post_id': post_id, 'send_time': send_time},
                {'$set': {'notified': True}}
            )
            
            # Enviar notificación final
            await send_deletion_notification(bot, post_id, stats)
            
    except Exception as e:
        logger.error(f"Error actualizando estadísticas de eliminación: {e}")

async def send_deletion_notification(bot: Bot, post_id: str, stats: dict):
    """Envía notificación final de eliminación al administrador"""
    try:
        from database import db
        
        cuba_tz = pytz.timezone(TIMEZONE)
        send_time_formatted = stats['send_time'].strftime('%H:%M:%S - %d/%m/%Y')
        delete_time_formatted = stats['delete_time'].strftime('%H:%M:%S - %d/%m/%Y')
        
        notification_text = (
            f"🗑️ **Eliminación Automática Completada**\n\n"
            f"🕐 **Hora de envío:** {send_time_formatted}\n"
            f"🗑️ **Hora de eliminación:** {delete_time_formatted}\n"
            f"📝 **Post:** {stats['post_name']}\n"
            f"📺 **Canales totales:** {stats['total_channels']}\n"
            f"✅ **Eliminados:** {stats['deleted_count']}\n"
            f"❌ **Eliminación fallida:** {stats['failed_count']}\n\n"
        )
        
        # Añadir razones de fallo si las hay
        if stats.get('failed_reasons'):
            notification_text += "**Razones de fallo:**\n"
            unique_reasons = list(set(stats['failed_reasons']))  # Eliminar duplicados
            for i, reason in enumerate(unique_reasons[:5], 1):  # Mostrar solo las primeras 5
                notification_text += f"{i}. {reason}\n"
            if len(unique_reasons) > 5:
                notification_text += f"... y {len(unique_reasons) - 5} razones más\n"
        
        # Enviar notificación
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=notification_text,
            parse_mode='Markdown'
        )
        
        # Eliminar el mensaje de notificación original
        notification_msg = db.notification_messages.find_one({
            'post_id': post_id,
            'send_time': stats['send_time'],
            'deleted': False
        })
        
        if notification_msg:
            try:
                await bot.delete_message(
                    chat_id=ADMIN_ID,
                    message_id=notification_msg['message_id']
                )
                
                # Marcar como eliminado
                db.notification_messages.update_one(
                    {'_id': notification_msg['_id']},
                    {'$set': {'deleted': True}}
                )
                
                logger.info(f"Eliminado mensaje de notificación original para post {post_id}")
                
            except Exception as e:
                logger.warning(f"No se pudo eliminar mensaje de notificación: {e}")
        
        logger.info(f"Notificación de eliminación enviada para post {post_id}")
        
    except Exception as e:
        logger.error(f"Error enviando notificación de eliminación: {e}")

async def delete_all_post_messages_now(bot: Bot, post_id: str):
    """Elimina inmediatamente todos los mensajes activos de un post"""
    try:
        from database import db
        
        # Buscar mensajes pendientes de eliminación
        pending_messages = list(db.sent_messages.find({
            'post_id': post_id,
            'deleted': False
        }))
        
        if not pending_messages:
            logger.info(f"No hay mensajes pendientes para eliminar del post {post_id}")
            return
        
        deleted_count = 0
        failed_count = 0
        failed_reasons = []
        
        # Obtener información del post
        post = Post.find_by_id(post_id)
        post_name = post.name if post else f"Post {post_id}"
        
        # Obtener el tiempo de envío más reciente
        latest_send_time = max([msg['send_time'] for msg in pending_messages])
        cuba_tz = pytz.timezone(TIMEZONE)
        delete_time = datetime.now(cuba_tz)
        
        for msg_info in pending_messages:
            try:
                await bot.delete_message(
                    chat_id=msg_info['channel_id'],
                    message_id=msg_info['message_id']
                )
                
                # Marcar como eliminado
                db.sent_messages.update_one(
                    {'_id': msg_info['_id']},
                    {'$set': {'deleted': True, 'deleted_at': datetime.utcnow()}}
                )
                
                deleted_count += 1
                logger.info(f"Eliminado mensaje {msg_info['message_id']} de {msg_info['channel_id']}")
                
            except Exception as e:
                failed_count += 1
                failed_reasons.append(str(e))
                logger.error(f"Error eliminando mensaje {msg_info['message_id']}: {e}")
        
        # Cancelar trabajos de eliminación programada
        for msg_info in pending_messages:
            job_id = f"delete_{post_id}_{msg_info['channel_id']}_{msg_info['message_id']}"
            if scheduler.get_job(job_id):
                scheduler.remove_job(job_id)
        
        # Enviar notificación de eliminación manual
        await send_manual_deletion_notification(
            bot, post_id, post_name, latest_send_time, delete_time, 
            len(pending_messages), deleted_count, failed_count, failed_reasons
        )
        
        logger.info(f"Eliminación manual completada: {deleted_count} exitosos, {failed_count} fallidos")
        
    except Exception as e:
        logger.error(f"Error en eliminación manual: {e}")

async def send_manual_deletion_notification(bot: Bot, post_id: str, post_name: str, 
                                           send_time: datetime, delete_time: datetime,
                                           total_channels: int, deleted_count: int, 
                                           failed_count: int, failed_reasons: list):
    """Envía notificación de eliminación manual"""
    try:
        from database import db
        
        send_time_formatted = send_time.strftime('%H:%M:%S - %d/%m/%Y')
        delete_time_formatted = delete_time.strftime('%H:%M:%S - %d/%m/%Y')
        
        notification_text = (
            f"🗑️ **Eliminación Manual Completada**\n\n"
            f"🕐 **Hora de envío:** {send_time_formatted}\n"
            f"🗑️ **Hora de eliminación:** {delete_time_formatted}\n"
            f"📝 **Post:** {post_name}\n"
            f"📺 **Canales totales:** {total_channels}\n"
            f"✅ **Eliminados:** {deleted_count}\n"
            f"❌ **Eliminación fallida:** {failed_count}\n\n"
        )
        
        # Añadir razones de fallo si las hay
        if failed_reasons:
            notification_text += "**Razones de fallo:**\n"
            unique_reasons = list(set(failed_reasons))  # Eliminar duplicados
            for i, reason in enumerate(unique_reasons[:5], 1):  # Mostrar solo las primeras 5
                notification_text += f"{i}. {reason}\n"
            if len(unique_reasons) > 5:
                notification_text += f"... y {len(unique_reasons) - 5} razones más\n"
        
        # Enviar notificación
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=notification_text,
            parse_mode='Markdown'
        )
        
        # Eliminar mensaje de notificación original si existe
        notification_msg = db.notification_messages.find_one({
            'post_id': post_id,
            'send_time': send_time,
            'deleted': False
        })
        
        if notification_msg:
            try:
                await bot.delete_message(
                    chat_id=ADMIN_ID,
                    message_id=notification_msg['message_id']
                )
                
                # Marcar como eliminado
                db.notification_messages.update_one(
                    {'_id': notification_msg['_id']},
                    {'$set': {'deleted': True}}
                )
                
                logger.info(f"Eliminado mensaje de notificación original para post {post_id}")
                
            except Exception as e:
                logger.warning(f"No se pudo eliminar mensaje de notificación: {e}")
        
        logger.info(f"Notificación de eliminación manual enviada para post {post_id}")
        
    except Exception as e:
        logger.error(f"Error enviando notificación de eliminación manual: {e}")

def schedule_message_deletion(bot: Bot, channel_id: str, message_id: int, hours: int):
    """Programar eliminación de mensaje específico"""
    cuba_tz = pytz.timezone(TIMEZONE)
    delete_time = datetime.now(cuba_tz) + timedelta(hours=hours)
    scheduler.add_job(
        delete_message,
        trigger='date',
        run_date=delete_time,
        args=[bot, channel_id, message_id],
        id=f"delete_manual_{channel_id}_{message_id}",
        replace_existing=True
    )

async def delete_message(bot: Bot, channel_id: str, message_id: int):
    """Eliminar mensaje simple sin notificación"""
    try:
        await bot.delete_message(chat_id=channel_id, message_id=message_id)
        logger.info(f"Eliminado mensaje {message_id} de {channel_id}")
    except Exception as e:
        logger.error(f"Error eliminando mensaje {message_id}: {e}")

def reschedule_post_job(bot: Bot, post_id: str):
    try:
        post = Post.find_by_id(post_id)
        schedule = PostSchedule.find_by_post_id(post_id)
        
        if post and schedule:
            schedule_post(bot, post, schedule)
            logger.info(f"Reprogramado post {post_id}")
    except Exception as e:
        logger.error(f"Error rescheduling post {post_id}: {e}")

def remove_post_jobs(post_id: str):
    send_job_id = f"send_{post_id}"
    if scheduler.get_job(send_job_id):
        scheduler.remove_job(send_job_id)
        logger.info(f"Eliminado trabajo {send_job_id}")

def stop_scheduler():
    if scheduler:
        scheduler.shutdown()
        logger.info("Scheduler detenido")
