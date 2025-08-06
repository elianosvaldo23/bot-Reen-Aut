from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import ContextTypes
from database import get_session, Post, PostSchedule, Channel, PostChannel, ScheduledJob
from config import ADMIN_ID, MAX_POSTS, MAX_CHANNELS_PER_POST
import re
import logging

logger = logging.getLogger(__name__)

def admin_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id != ADMIN_ID:
            if update.message:
                await update.message.reply_text("❌ No tienes permisos de administrador.")
            elif update.callback_query:
                await update.callback_query.answer("❌ No tienes permisos de administrador.", show_alert=True)
            return
        return await func(update, context)
    return wrapper

@admin_only
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📋 Mis Posts", callback_data="list_posts")],
        [InlineKeyboardButton("➕ Crear Post", callback_data="create_post")],
        [InlineKeyboardButton("📺 Gestionar Canales", callback_data="manage_channels")],
        [InlineKeyboardButton("📊 Estadísticas", callback_data="statistics")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    message_text = (
        "🤖 **Bienvenido al Auto Post Bot**\n\n"
        "Selecciona una opción:"
    )
    
    if update.message:
        await update.message.reply_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')
    elif update.callback_query:
        await update.callback_query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')

@admin_only
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    # Navegación principal
    if data == "back_main":
        await start(update, context)
    elif data == "list_posts":
        await list_posts(query)
    elif data == "create_post":
        await create_post_prompt(query, context)
    elif data == "manage_channels":
        await manage_channels_menu(query)
    elif data == "statistics":
        await show_statistics(query)
    
    # Acciones de posts específicos
    elif data.startswith("post_"):
        await handle_post_action(query, data)
    elif data.startswith("configure_schedule_"):
        post_id = int(data.split('_')[2])
        await configure_schedule_menu(query, post_id)
    elif data.startswith("configure_channels_"):
        post_id = int(data.split('_')[2])
        await configure_channels_menu(query, context, post_id)
    elif data.startswith("delete_post_"):
        post_id = int(data.split('_')[2])
        await confirm_delete_post(query, post_id)
    elif data.startswith("confirm_delete_"):
        post_id = int(data.split('_')[2])
        await delete_post(query, post_id)
    
    # Configuración de horarios
    elif data.startswith("set_time_"):
        post_id = int(data.split('_')[2])
        await prompt_set_time(query, context, post_id)
    elif data.startswith("set_delete_"):
        post_id = int(data.split('_')[2])
        await prompt_set_delete_hours(query, context, post_id)
    elif data.startswith("set_days_"):
        post_id = int(data.split('_')[2])
        await configure_days_menu(query, context, post_id)
    elif data.startswith("toggle_day_"):
        parts = data.split('_')
        post_id, day_num = int(parts[2]), int(parts[3])
        await toggle_day(query, context, post_id, day_num)
    elif data.startswith("save_days_"):
        post_id = int(data.split('_')[2])
        await save_days(query, context, post_id)
    
    # Nuevas funciones
    elif data.startswith("toggle_pin_"):
        post_id = int(data.split('_')[2])
        await toggle_pin_message(query, context, post_id)
    elif data.startswith("toggle_forward_"):
        post_id = int(data.split('_')[2])
        await toggle_forward_original(query, context, post_id)
    elif data.startswith("send_now_"):
        post_id = int(data.split('_')[2])
        await send_post_manually(query, context, post_id)
    elif data.startswith("confirm_send_"):
        post_id = int(data.split('_')[2])
        await confirm_manual_send(query, context, post_id)
    elif data.startswith("preview_"):
        post_id = int(data.split('_')[1])
        await preview_post(query, context, post_id)
    elif data.startswith("send_preview_"):
        post_id = int(data.split('_')[2])
        await send_preview_to_admin(query, context, post_id)
    
    # Gestión de canales
    elif data == "add_channel":
        await prompt_add_channel(query, context)
    elif data == "remove_channel":
        await show_remove_channel_menu(query)
    elif data == "list_channels":
        await show_channels_list(query)
    elif data.startswith("remove_channel_"):
        channel_id = int(data.split('_')[2])
        await remove_channel(query, channel_id)
    
    # Asignación de canales a posts
    elif data.startswith("toggle_channel_"):
        parts = data.split('_')
        post_id, channel_id = int(parts[2]), parts[3]
        await toggle_channel_assignment(query, context, post_id, channel_id)
    elif data.startswith("save_assignments_"):
        post_id = int(data.split('_')[2])
        await save_channel_assignments(query, context, post_id)

async def list_posts(query):
    session = get_session()
    posts = session.query(Post).filter_by(is_active=True).all()
    session.close()
    
    if not posts:
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="back_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("📭 No hay posts activos.", reply_markup=reply_markup)
        return
    
    keyboard = []
    for post in posts:
        keyboard.append([
            InlineKeyboardButton(
                f"📄 {post.name} ({post.content_type.title()})",
                callback_data=f"post_{post.id}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="back_main")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📋 **Posts Activos:**",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def handle_post_action(query, data):
    post_id = int(data.split('_')[1])
    session = get_session()
    
    post = session.query(Post).filter_by(id=post_id).first()
    if not post:
        await query.edit_message_text("❌ Post no encontrado.")
        session.close()
        return
    
    schedule = session.query(PostSchedule).filter_by(post_id=post_id).first()
    assigned_channels = session.query(PostChannel).filter_by(post_id=post_id).count()
    
    session.close()
    
    # Información del horario
    schedule_info = "No configurado"
    if schedule:
        days_map = {1: "L", 2: "M", 3: "X", 4: "J", 5: "V", 6: "S", 7: "D"}
        current_days = [int(d) for d in schedule.days_of_week.split(',')]
        days_display = "".join([days_map[d] for d in current_days])
        schedule_info = f"{schedule.send_time} ({days_display}) - Eliminar: {schedule.delete_after_hours}h"
    
    keyboard = [
        [InlineKeyboardButton("⏰ Configurar Horario", callback_data=f"configure_schedule_{post.id}")],
        [InlineKeyboardButton("📺 Asignar Canales", callback_data=f"configure_channels_{post.id}")],
        [InlineKeyboardButton("👀 Vista Previa", callback_data=f"preview_{post.id}"),
         InlineKeyboardButton("📤 Enviar Ahora", callback_data=f"send_now_{post.id}")],
        [InlineKeyboardButton("🗑️ Eliminar Post", callback_data=f"delete_post_{post.id}")],
        [InlineKeyboardButton("🔙 Volver", callback_data="list_posts")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"**📄 {post.name}**\n\n"
        f"**Tipo:** {post.content_type.title()}\n"
        f"**Horario:** {schedule_info}\n"
        f"**Canales:** {assigned_channels} asignados\n"
        f"**Fuente:** `{post.source_channel}`",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# --- CREAR POSTS ---
async def create_post_prompt(query, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['state'] = 'waiting_for_post'
    
    await query.edit_message_text(
        "📤 **Para crear un post:**\n\n"
        "1. Ve al canal fuente\n"
        "2. **Reenvía** el mensaje al bot\n"
        "3. El bot detectará automáticamente el contenido\n\n"
        "**Tipos soportados:**\n"
        "• Texto, Fotos, Videos\n"
        "• Audio, Documentos, GIFs\n"
        "• Stickers, Mensajes de voz\n\n"
        "⚠️ **Importante:** Usa 'Reenviar', no copiar",
        parse_mode='Markdown'
    )

async def handle_post_creation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    message = update.message
    
    # Verificar si es un mensaje reenviado o si estamos esperando contenido
    if not message.forward_origin and context.user_data.get('state') != 'waiting_for_post':
        return
    
    # Si no estamos en estado de espera, activarlo automáticamente para mensajes reenviados
    if message.forward_origin and context.user_data.get('state') != 'waiting_for_post':
        context.user_data['state'] = 'waiting_for_post'
    
    session = get_session()
    try:
        post_count = session.query(Post).filter_by(is_active=True).count()
        
        if post_count >= MAX_POSTS:
            await message.reply_text(f"❌ Máximo {MAX_POSTS} posts permitidos. Elimina uno existente primero.")
            context.user_data.pop('state', None)
            return
        
        # Detectar tipo de contenido
        content_type, file_id, text = extract_content_info(message)
        
        if not content_type:
            await message.reply_text("❌ Tipo de contenido no soportado.")
            context.user_data.pop('state', None)
            return
        
        # Obtener información de la fuente
        source_channel = None
        source_message_id = None
        
        if message.forward_origin:
            if hasattr(message.forward_origin, 'chat'):
                source_channel = str(message.forward_origin.chat.id)
                source_message_id = message.forward_origin.message_id
            elif hasattr(message.forward_origin, 'sender_user'):
                source_channel = str(message.forward_origin.sender_user.id)
                source_message_id = message.message_id
        else:
            source_channel = str(message.chat.id)
            source_message_id = message.message_id
        
        # Crear post
        post_name = f"Post {post_count + 1}"
        if text and len(text) > 20:
            post_name = text[:20] + "..."
        
        post = Post(
            name=post_name,
            source_channel=source_channel,
            source_message_id=source_message_id,
            content_type=content_type,
            content_text=text or "",
            file_id=file_id
        )
        
        session.add(post)
        session.commit()
        
        # Crear horario por defecto
        schedule = PostSchedule(
            post_id=post.id,
            send_time="09:00",
            delete_after_hours=24,
            days_of_week="1,2,3,4,5,6,7",
            pin_message=False,
            forward_original=True
        )
        session.add(schedule)
        session.commit()
        
        context.user_data.pop('state', None)
        
        # Crear botones de acción rápida
        keyboard = [
            [InlineKeyboardButton("⚙️ Configurar", callback_data=f"post_{post.id}")],
            [InlineKeyboardButton("📺 Asignar Canales", callback_data=f"configure_channels_{post.id}")],
            [InlineKeyboardButton("📤 Enviar Ahora", callback_data=f"send_now_{post.id}")],
            [InlineKeyboardButton("🏠 Menú Principal", callback_data="back_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await message.reply_text(
            f"✅ **Post creado exitosamente!**\n\n"
            f"**ID:** {post.id}\n"
            f"**Nombre:** {post.name}\n"
            f"**Tipo:** {content_type.title()}\n"
            f"**Fuente:** `{source_channel}`\n\n"
            f"¿Qué quieres hacer ahora?",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error creating post: {e}")
        await message.reply_text(f"❌ Error al crear el post: {str(e)}")
        context.user_data.pop('state', None)
    finally:
        session.close()

def extract_content_info(message):
    """Extrae información del contenido del mensaje"""
    content_type = None
    file_id = None
    text = None
    
    if message.text:
        content_type = 'text'
        text = message.text
    elif message.photo:
        content_type = 'photo'
        file_id = message.photo[-1].file_id
        text = message.caption
    elif message.video:
        content_type = 'video'
        file_id = message.video.file_id
        text = message.caption
    elif message.audio:
        content_type = 'audio'
        file_id = message.audio.file_id
        text = message.caption
    elif message.document:
        content_type = 'document'
        file_id = message.document.file_id
        text = message.caption
    elif message.animation:
        content_type = 'animation'
        file_id = message.animation.file_id
        text = message.caption
    elif message.sticker:
        content_type = 'sticker'
        file_id = message.sticker.file_id
        text = message.sticker.emoji
    elif message.voice:
        content_type = 'voice'
        file_id = message.voice.file_id
        text = message.caption
    
    return content_type, file_id, text

# --- CONFIGURACIÓN DE HORARIOS ---
async def configure_schedule_menu(query, post_id):
    session = get_session()
    post = session.query(Post).filter_by(id=post_id).first()
    schedule = session.query(PostSchedule).filter_by(post_id=post_id).first()
    session.close()
    
    if not post or not schedule:
        await query.edit_message_text("❌ Post o horario no encontrado.")
        return
    
    days_map = {1: "Lun", 2: "Mar", 3: "Mié", 4: "Jue", 5: "Vie", 6: "Sáb", 7: "Dom"}
    current_days = [int(d) for d in schedule.days_of_week.split(',')]
    days_display = ", ".join([days_map[d] for d in current_days])
    
    pin_status = "✅" if schedule.pin_message else "❌"
    forward_status = "✅" if schedule.forward_original else "❌"
    
    keyboard = [
        [InlineKeyboardButton(f"🕐 Hora: {schedule.send_time}", callback_data=f"set_time_{post_id}")],
        [InlineKeyboardButton(f"⏰ Eliminar después: {schedule.delete_after_hours}h", callback_data=f"set_delete_{post_id}")],
        [InlineKeyboardButton(f"📅 Días: {days_display}", callback_data=f"set_days_{post_id}")],
        [InlineKeyboardButton(f"📌 Fijar mensaje: {pin_status}", callback_data=f"toggle_pin_{post_id}")],
        [InlineKeyboardButton(f"📤 Reenviar original: {forward_status}", callback_data=f"toggle_forward_{post_id}")],
        [InlineKeyboardButton("🔙 Volver", callback_data=f"post_{post_id}")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"⚙️ **Configurar Horario**\n\n"
        f"**Post:** {post.name}\n\n"
        f"Selecciona qué configurar:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def toggle_pin_message(query, context: ContextTypes.DEFAULT_TYPE, post_id):
    session = get_session()
    try:
        schedule = session.query(PostSchedule).filter_by(post_id=post_id).first()
        if schedule:
            schedule.pin_message = not schedule.pin_message
            session.commit()
            
            status = "activado" if schedule.pin_message else "desactivado"
            await query.answer(f"✅ Fijar mensaje {status}")
            await configure_schedule_menu(query, post_id)
        else:
            await query.edit_message_text("❌ Horario no encontrado.")
    except Exception as e:
        session.rollback()
        logger.error(f"Error toggling pin: {e}")
        await query.edit_message_text(f"❌ Error: {str(e)}")
    finally:
        session.close()

async def toggle_forward_original(query, context: ContextTypes.DEFAULT_TYPE, post_id):
    session = get_session()
    try:
        schedule = session.query(PostSchedule).filter_by(post_id=post_id).first()
        if schedule:
            schedule.forward_original = not schedule.forward_original
            session.commit()
            
            status = "activado" if schedule.forward_original else "desactivado"
            await query.answer(f"✅ Reenvío original {status}")
            await configure_schedule_menu(query, post_id)
        else:
            await query.edit_message_text("❌ Horario no encontrado.")
    except Exception as e:
        session.rollback()
        logger.error(f"Error toggling forward: {e}")
        await query.edit_message_text(f"❌ Error: {str(e)}")
    finally:
        session.close()

async def prompt_set_time(query, context: ContextTypes.DEFAULT_TYPE, post_id):
    context.user_data['state'] = 'waiting_time'
    context.user_data['post_id'] = post_id
    
    await query.edit_message_text(
        "🕐 **Configurar Hora de Envío**\n\n"
        "Envía la hora en formato **HH:MM**\n"
        "Ejemplos: `09:30`, `14:00`, `20:15`",
        parse_mode='Markdown'
    )

async def prompt_set_delete_hours(query, context: ContextTypes.DEFAULT_TYPE, post_id):
    context.user_data['state'] = 'waiting_delete_hours'
    context.user_data['post_id'] = post_id
    
    await query.edit_message_text(
        "⏰ **Horas para Eliminar**\n\n"
        "Envía el número de horas (1-48)\n"
        "Ejemplos: `1`, `6`, `24`\n\n"
        "Envía `0` para no eliminar automáticamente",
        parse_mode='Markdown'
    )

async def configure_days_menu(query, context: ContextTypes.DEFAULT_TYPE, post_id):
    session = get_session()
    schedule = session.query(PostSchedule).filter_by(post_id=post_id).first()
    session.close()
    
    if not schedule:
        await query.edit_message_text("❌ Horario no encontrado.")
        return
    
    current_days = [int(d) for d in schedule.days_of_week.split(',')]
    context.user_data['selected_days'] = current_days.copy()
    context.user_data['configuring_post_id'] = post_id
    
    await update_days_menu(query, context, post_id)

async def update_days_menu(query, context: ContextTypes.DEFAULT_TYPE, post_id):
    selected_days = context.user_data.get('selected_days', [])
    
    days_map = {
        1: "Lunes", 2: "Martes", 3: "Miércoles", 4: "Jueves",
        5: "Viernes", 6: "Sábado", 7: "Domingo"
    }
    
    keyboard = []
    for day_num, day_name in days_map.items():
        status = "✅" if day_num in selected_days else "❌"
        keyboard.append([
            InlineKeyboardButton(
                f"{status} {day_name}",
                callback_data=f"toggle_day_{post_id}_{day_num}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("💾 Guardar", callback_data=f"save_days_{post_id}")])
    keyboard.append([InlineKeyboardButton("🔙 Cancelar", callback_data=f"configure_schedule_{post_id}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📅 **Seleccionar Días**\n\n"
        "Haz clic para activar/desactivar días:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def toggle_day(query, context: ContextTypes.DEFAULT_TYPE, post_id, day_num):
    selected_days = context.user_data.get('selected_days', [])
    
    if day_num in selected_days:
        selected_days.remove(day_num)
    else:
        selected_days.append(day_num)
    
    context.user_data['selected_days'] = selected_days
    await update_days_menu(query, context, post_id)

async def save_days(query, context: ContextTypes.DEFAULT_TYPE, post_id):
    selected_days = context.user_data.get('selected_days', [])
    
    if not selected_days:
        await query.answer("❌ Selecciona al menos un día", show_alert=True)
        return
    
    session = get_session()
    try:
        schedule = session.query(PostSchedule).filter_by(post_id=post_id).first()
        if schedule:
            schedule.days_of_week = ','.join(map(str, sorted(selected_days)))
            session.commit()
            
            # Reprogramar en el scheduler
            from scheduler import reschedule_post_job
            reschedule_post_job(query.bot, post_id)
            
            await query.answer("✅ Días guardados correctamente")
            context.user_data.pop('selected_days', None)
            context.user_data.pop('configuring_post_id', None)
            
            await configure_schedule_menu(query, post_id)
        else:
            await query.edit_message_text("❌ Horario no encontrado.")
    except Exception as e:
        session.rollback()
        logger.error(f"Error saving days: {e}")
        await query.edit_message_text(f"❌ Error al guardar: {str(e)}")
    finally:
        session.close()

# --- ENVÍO MANUAL Y VISTA PREVIA ---
async def send_post_manually(query, context: ContextTypes.DEFAULT_TYPE, post_id):
    """Enviar post manualmente a todos los canales asignados"""
    session = get_session()
    try:
        post = session.query(Post).filter_by(id=post_id, is_active=True).first()
        if not post:
            await query.edit_message_text("❌ Post no encontrado.")
            return
        
        post_channels = session.query(PostChannel).filter_by(post_id=post_id).all()
        if not post_channels:
            await query.edit_message_text("❌ No hay canales asignados a este post.")
            return
        
        schedule = session.query(PostSchedule).filter_by(post_id=post_id).first()
        
        # Mensaje de confirmación
        keyboard = [
            [InlineKeyboardButton("✅ Sí, Enviar", callback_data=f"confirm_send_{post_id}")],
            [InlineKeyboardButton("❌ Cancelar", callback_data=f"post_{post_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"📤 **Envío Manual**\n\n"
            f"**Post:** {post.name}\n"
            f"**Canales:** {len(post_channels)}\n"
            f"**Tipo:** {post.content_type.title()}\n\n"
            f"¿Confirmas el envío manual?",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    finally:
        session.close()

async def confirm_manual_send(query, context: ContextTypes.DEFAULT_TYPE, post_id):
    """Confirmar y ejecutar envío manual"""
    await query.edit_message_text("📤 Enviando post...")
    
    session = get_session()
    try:
        post = session.query(Post).filter_by(id=post_id, is_active=True).first()
        post_channels = session.query(PostChannel).filter_by(post_id=post_id).all()
        schedule = session.query(PostSchedule).filter_by(post_id=post_id).first()
        
        if not post or not post_channels:
            await query.edit_message_text("❌ Error: Post o canales no encontrados.")
            return
        
        sent_count = 0
        error_count = 0
        sent_messages = []
        
        for pc in post_channels:
            try:
                # Enviar mensaje
                message = await send_content_to_channel(context.bot, pc.channel_id, post, schedule)
                
                if message:
                    sent_count += 1
                    sent_messages.append({
                        'channel_id': pc.channel_id,
                        'message_id': message.message_id
                    })
                    
                    # Fijar si está configurado
                    if schedule and schedule.pin_message:
                        try:
                            await context.bot.pin_chat_message(
                                chat_id=pc.channel_id,
                                message_id=message.message_id,
                                disable_notification=True
                            )
                        except Exception as pin_error:
                            logger.warning(f"No se pudo fijar mensaje: {pin_error}")
                    
                    # Programar eliminación si está configurado
                    if schedule and schedule.delete_after_hours > 0:
                        from scheduler import schedule_message_deletion
                        schedule_message_deletion(
                            context.bot, 
                            pc.channel_id, 
                            message.message_id, 
                            schedule.delete_after_hours
                        )
                else:
                    error_count += 1
                    
            except Exception as e:
                error_count += 1
                logger.error(f"Error sending to channel {pc.channel_id}: {e}")
        
        # Mostrar resultado
        result_text = f"📊 **Resultado del Envío**\n\n"
        result_text += f"✅ **Enviados:** {sent_count}\n"
        result_text += f"❌ **Errores:** {error_count}\n"
        result_text += f"📺 **Total canales:** {len(post_channels)}\n\n"
        
        if schedule and schedule.delete_after_hours > 0:
            result_text += f"⏰ **Eliminación programada:** {schedule.delete_after_hours}h\n"
        
        if schedule and schedule.pin_message:
            result_text += f"📌 **Mensajes fijados**\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data=f"post_{post_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            result_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error in manual send: {e}")
        await query.edit_message_text(f"❌ Error durante el envío: {str(e)}")
    finally:
        session.close()

async def preview_post(query, context: ContextTypes.DEFAULT_TYPE, post_id):
    """Mostrar vista previa del post"""
    session = get_session()
    try:
        post = session.query(Post).filter_by(id=post_id).first()
        if not post:
            await query.edit_message_text("❌ Post no encontrado.")
            return
        
        # Enviar vista previa al admin
        preview_text = f"👀 **Vista Previa del Post**\n\n"
        
        if post.content_type == 'text':
            preview_text += f"**Contenido:**\n{post.content_text}"
        else:
            preview_text += f"**Tipo:** {post.content_type.title()}\n"
            if post.content_text:
                preview_text += f"**Caption:** {post.content_text}\n"
            preview_text += f"**Archivo ID:** `{post.file_id}`"
        
        keyboard = [
            [InlineKeyboardButton("📤 Enviar Vista Previa", callback_data=f"send_preview_{post_id}")],
            [InlineKeyboardButton("🔙 Volver", callback_data=f"post_{post_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            preview_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    finally:
        session.close()

async def send_preview_to_admin(query, context: ContextTypes.DEFAULT_TYPE, post_id):
    """Enviar vista previa real del contenido"""
    session = get_session()
    try:
        post = session.query(Post).filter_by(id=post_id).first()
        if not post:
            await query.answer("❌ Post no encontrado")
            return
        
        # Enviar el contenido real al admin como vista previa
        admin_id = query.from_user.id
        
        try:
            await send_content_to_channel(context.bot, admin_id, post)
            await query.answer("✅ Vista previa enviada")
        except Exception as e:
            await query.answer(f"❌ Error: {str(e)}")
            
    finally:
        session.close()

async def send_content_to_channel(bot: Bot, channel_id: str, post: Post, schedule: PostSchedule = None):
    """Envía contenido a un canal específico"""
    try:
        # Si está configurado para reenviar original y tenemos la info
        if schedule and schedule.forward_original and post.source_channel and post.source_message_id:
            try:
                return await bot.forward_message(
                    chat_id=channel_id,
                    from_chat_id=post.source_channel,
                    message_id=post.source_message_id
                )
            except Exception as e:
                logger.warning(f"No se pudo reenviar original: {e}")
        
        # Enviar contenido guardado
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
        logger.error(f"Error sending content to {channel_id}: {e}")
        return None

# --- GESTIÓN DE CANALES ---
async def manage_channels_menu(query):
    keyboard = [
        [InlineKeyboardButton("➕ Añadir Canal", callback_data="add_channel")],
        [InlineKeyboardButton("➖ Eliminar Canal", callback_data="remove_channel")],
        [InlineKeyboardButton("📋 Ver Canales", callback_data="list_channels")],
        [InlineKeyboardButton("🔙 Volver", callback_data="back_main")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "📺 **Gestión de Canales**\n\n"
        "Selecciona una opción:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def verify_bot_permissions(bot: Bot, channel_id: str):
    """Verifica si el bot es administrador del canal"""
    try:
        chat_member = await bot.get_chat_member(channel_id, bot.id)
        
        if chat_member.status not in ['administrator', 'creator']:
            return False, f"El bot no es administrador en el canal"
        
        # Verificar permisos específicos
        if chat_member.status == 'administrator':
            if not chat_member.can_post_messages:
                return False, f"El bot no tiene permisos para enviar mensajes"
            if not chat_member.can_delete_messages:
                return False, f"El bot no tiene permisos para eliminar mensajes"
            if not chat_member.can_pin_messages:
                return False, f"El bot no tiene permisos para fijar mensajes"
        
        return True, "Permisos correctos"
        
    except Exception as e:
        return False, f"Error verificando permisos: {str(e)}"

async def prompt_add_channel(query, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['state'] = 'waiting_channel'
    
    await query.edit_message_text(
        "➕ **Añadir Canal**\n\n"
        "Envía el canal en uno de estos formatos:\n"
        "• `@nombre_canal`\n"
        "• `https://t.me/nombre_canal`\n"
        "• `-1001234567890` (ID)\n\n"
        "⚠️ El bot debe ser admin en el canal",
        parse_mode='Markdown'
    )

async def show_channels_list(query):
    session = get_session()
    channels = session.query(Channel).all()
    session.close()
    
    if not channels:
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="manage_channels")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("📭 No hay canales registrados.", reply_markup=reply_markup)
        return
    
    message = "📺 **Canales Registrados:**\n\n"
    for i, channel in enumerate(channels, 1):
        name = channel.channel_name or channel.channel_username or channel.channel_id
        message += f"{i}. `{name}`\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="manage_channels")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')

async def show_remove_channel_menu(query):
    session = get_session()
    channels = session.query(Channel).all()
    session.close()
    
    if not channels:
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="manage_channels")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("📭 No hay canales para eliminar.", reply_markup=reply_markup)
        return
    
    keyboard = []
    for channel in channels:
        name = channel.channel_name or channel.channel_username or channel.channel_id
        keyboard.append([
            InlineKeyboardButton(f"🗑️ {name}", callback_data=f"remove_channel_{channel.id}")
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="manage_channels")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "➖ **Eliminar Canal**\n\nSelecciona el canal:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def remove_channel(query, channel_id):
    session = get_session()
    try:
        channel = session.query(Channel).filter_by(id=channel_id).first()
        if channel:
            # Eliminar asignaciones
            session.query(PostChannel).filter_by(channel_id=channel.channel_id).delete()
            session.delete(channel)
            session.commit()
            
            await query.answer("✅ Canal eliminado correctamente")
            await manage_channels_menu(query)
        else:
            await query.edit_message_text("❌ Canal no encontrado.")
    except Exception as e:
        session.rollback()
        logger.error(f"Error removing channel: {e}")
        await query.edit_message_text(f"❌ Error: {str(e)}")
    finally:
        session.close()

# --- ASIGNACIÓN DE CANALES A POSTS ---
async def configure_channels_menu(query, context: ContextTypes.DEFAULT_TYPE, post_id):
    session = get_session()
    
    all_channels = session.query(Channel).all()
    if not all_channels:
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data=f"post_{post_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "❌ No hay canales disponibles.\nPrimero añade canales.",
            reply_markup=reply_markup
        )
        session.close()
        return
    
    # Obtener canales asignados actualmente
    assigned = session.query(PostChannel).filter_by(post_id=post_id).all()
    assigned_ids = [pc.channel_id for pc in assigned]
    
    session.close()
    
    # Guardar selección actual
    context.user_data['channel_assignments'] = assigned_ids.copy()
    context.user_data['assigning_post_id'] = post_id
    
    await update_channels_menu(query, context, post_id)

async def update_channels_menu(query, context: ContextTypes.DEFAULT_TYPE, post_id):
    session = get_session()
    all_channels = session.query(Channel).all()
    session.close()
    
    selected_channels = context.user_data.get('channel_assignments', [])
    
    keyboard = []
    for channel in all_channels:
        status = "✅" if channel.channel_id in selected_channels else "❌"
        name = channel.channel_name or channel.channel_username or channel.channel_id
        keyboard.append([
            InlineKeyboardButton(
                f"{status} {name}",
                callback_data=f"toggle_channel_{post_id}_{channel.channel_id}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("💾 Guardar", callback_data=f"save_assignments_{post_id}")])
    keyboard.append([InlineKeyboardButton("🔙 Cancelar", callback_data=f"post_{post_id}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"📺 **Asignar Canales**\n\n"
        f"Seleccionados: {len(selected_channels)}/{MAX_CHANNELS_PER_POST}",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def toggle_channel_assignment(query, context: ContextTypes.DEFAULT_TYPE, post_id, channel_id):
    selected_channels = context.user_data.get('channel_assignments', [])
    
    if channel_id in selected_channels:
        selected_channels.remove(channel_id)
    else:
        if len(selected_channels) >= MAX_CHANNELS_PER_POST:
            await query.answer(f"❌ Máximo {MAX_CHANNELS_PER_POST} canales", show_alert=True)
            return
        selected_channels.append(channel_id)
    
    context.user_data['channel_assignments'] = selected_channels
    await update_channels_menu(query, context, post_id)

async def save_channel_assignments(query, context: ContextTypes.DEFAULT_TYPE, post_id):
    selected_channels = context.user_data.get('channel_assignments', [])
    
    session = get_session()
    try:
        # Eliminar asignaciones existentes
        session.query(PostChannel).filter_by(post_id=post_id).delete()
        
        # Añadir nuevas asignaciones
        for channel_id in selected_channels:
            post_channel = PostChannel(post_id=post_id, channel_id=channel_id)
            session.add(post_channel)
        
        session.commit()
        
        context.user_data.pop('channel_assignments', None)
        context.user_data.pop('assigning_post_id', None)
        
        await query.answer(f"✅ {len(selected_channels)} canales asignados")
        await handle_post_action(query, f"post_{post_id}")
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error saving assignments: {e}")
        await query.edit_message_text(f"❌ Error: {str(e)}")
    finally:
        session.close()

# --- ELIMINAR POSTS ---
async def confirm_delete_post(query, post_id):
    session = get_session()
    post = session.query(Post).filter_by(id=post_id).first()
    session.close()
    
    if not post:
        await query.edit_message_text("❌ Post no encontrado.")
        return
    
    keyboard = [
        [InlineKeyboardButton("🗑️ Sí, Eliminar", callback_data=f"confirm_delete_{post_id}")],
        [InlineKeyboardButton("❌ Cancelar", callback_data=f"post_{post_id}")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"⚠️ **Confirmar Eliminación**\n\n"
        f"¿Eliminar **{post.name}**?\n"
        f"Esta acción es irreversible.",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def delete_post(query, post_id):
    session = get_session()
    try:
        post = session.query(Post).filter_by(id=post_id).first()
        if post:
            # Eliminar registros relacionados
            session.query(PostChannel).filter_by(post_id=post_id).delete()
            session.query(PostSchedule).filter_by(post_id=post_id).delete()
            session.query(ScheduledJob).filter_by(post_id=post_id).delete()
            session.delete(post)
            session.commit()
            
            # Eliminar trabajos del scheduler
            from scheduler import remove_post_jobs
            remove_post_jobs(post_id)
            
            await query.answer("✅ Post eliminado")
            await list_posts(query)
        else:
            await query.edit_message_text("❌ Post no encontrado.")
    except Exception as e:
        session.rollback()
        logger.error(f"Error deleting post: {e}")
        await query.edit_message_text(f"❌ Error: {str(e)}")
    finally:
        session.close()

# --- ESTADÍSTICAS ---
async def show_statistics(query):
    session = get_session()
    
    total_posts = session.query(Post).filter_by(is_active=True).count()
    total_channels = session.query(Channel).count()
    total_schedules = session.query(PostSchedule).filter_by(is_enabled=True).count()
    
    session.close()
    
    keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="back_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    status = "🟢 Operativo" if total_posts > 0 else "🟡 Sin posts"
    
    await query.edit_message_text(
        f"📊 **Estadísticas del Bot**\n\n"
        f"**Posts Activos:** {total_posts}/{MAX_POSTS}\n"
        f"**Canales:** {total_channels}\n"
        f"**Horarios:** {total_schedules}\n"
        f"**Estado:** {status}",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# --- MANEJO DE ENTRADA DE TEXTO ---
async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    state = context.user_data.get('state')
    text = update.message.text.strip()
    
    if state == 'waiting_time':
        await handle_time_input(update, context, text)
    elif state == 'waiting_delete_hours':
        await handle_delete_hours_input(update, context, text)
    elif state == 'waiting_channel':
        await handle_channel_input(update, context, text)

async def handle_time_input(update, context, text):
    if not re.match(r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$', text):
        await update.message.reply_text("❌ Formato inválido. Usa HH:MM (ej: 09:30)")
        return
    
    post_id = context.user_data.get('post_id')
    session = get_session()
    
    try:
        schedule = session.query(PostSchedule).filter_by(post_id=post_id).first()
        if schedule:
            schedule.send_time = text
            session.commit()
            
            from scheduler import reschedule_post_job
            reschedule_post_job(context.bot, post_id)
            
            await update.message.reply_text(f"✅ Hora configurada: {text}")
            context.user_data.pop('state', None)
            context.user_data.pop('post_id', None)
        else:
            await update.message.reply_text("❌ Horario no encontrado.")
    except Exception as e:
        session.rollback()
        logger.error(f"Error setting time: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")
    finally:
        session.close()

async def handle_delete_hours_input(update, context, text):
    try:
        hours = int(text)
        if hours < 0 or hours > 48:
            await update.message.reply_text("❌ Debe ser entre 0 y 48 horas")
            return
    except ValueError:
        await update.message.reply_text("❌ Ingresa un número válido")
        return
    
    post_id = context.user_data.get('post_id')
    session = get_session()
    
    try:
        schedule = session.query(PostSchedule).filter_by(post_id=post_id).first()
        if schedule:
            schedule.delete_after_hours = hours
            session.commit()
            
            await update.message.reply_text(f"✅ Configurado: eliminar después de {hours} horas")
            context.user_data.pop('state', None)
            context.user_data.pop('post_id', None)
        else:
            await update.message.reply_text("❌ Horario no encontrado.")
    except Exception as e:
        session.rollback()
        logger.error(f"Error setting delete hours: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")
    finally:
        session.close()

async def handle_channel_input(update, context, text):
    channel_info = extract_channel_info(text)
    
    if not channel_info:
        await update.message.reply_text(
            "❌ Formato inválido. Usa:\n"
            "• @nombre_canal\n"
            "• https://t.me/nombre_canal\n"
            "• -1001234567890"
        )
        return
    
    # Mensaje de verificación
    verification_msg = await update.message.reply_text("🔍 Verificando canal y permisos...")
    
    session = get_session()
    try:
        # Verificar si ya existe
        existing = session.query(Channel).filter_by(channel_id=channel_info).first()
        if existing:
            await verification_msg.edit_text("❌ Este canal ya está registrado")
            return
        
        # Intentar obtener información del canal
        channel_name = None
        channel_username = None
        channel_id_final = channel_info
        
        try:
            chat = await context.bot.get_chat(channel_info)
            channel_id_final = str(chat.id)
            channel_name = chat.title
            channel_username = chat.username
            
            # Verificar permisos del bot
            has_permissions, permission_msg = await verify_bot_permissions(context.bot, channel_id_final)
            
            if not has_permissions:
                await verification_msg.edit_text(
                    f"⚠️ **Canal encontrado pero hay problemas:**\n\n"
                    f"**Canal:** {channel_name or channel_info}\n"
                    f"**Problema:** {permission_msg}\n\n"
                    f"**Solución:**\n"
                    f"1. Ve al canal\n"
                    f"2. Añade el bot como administrador\n"
                    f"3. Dale permisos para:\n"
                    f"   • Enviar mensajes\n"
                    f"   • Eliminar mensajes\n"
                    f"   • Fijar mensajes\n"
                    f"4. Intenta añadir el canal nuevamente",
                    parse_mode='Markdown'
                )
                return
            
        except Exception as e:
            await verification_msg.edit_text(
                f"❌ **No se pudo acceder al canal:**\n\n"
                f"**Error:** {str(e)}\n\n"
                f"**Posibles causas:**\n"
                f"• El canal no existe\n"
                f"• El bot no está en el canal\n"
                f"• El canal es privado\n"
                f"• Formato incorrecto"
            )
            return
        
        # Crear canal
        channel = Channel(
            channel_id=channel_id_final,
            channel_name=channel_name,
            channel_username=channel_username
        )
        
        session.add(channel)
        session.commit()
        
        context.user_data.pop('state', None)
        
        await verification_msg.edit_text(
            f"✅ **Canal añadido exitosamente!**\n\n"
            f"**Nombre:** {channel_name or 'Sin nombre'}\n"
            f"**Username:** @{channel_username or 'Sin username'}\n"
            f"**ID:** `{channel_id_final}`\n"
            f"**Permisos:** ✅ Verificados",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error adding channel: {e}")
        await verification_msg.edit_text(f"❌ Error: {str(e)}")
    finally:
        session.close()

def extract_channel_info(text):
    """Extrae información del canal del texto"""
    patterns = [
        r't\.me/([a-zA-Z0-9_]+)',  # t.me/username
        r'@([a-zA-Z0-9_]+)',       # @username
        r'(-100\d+)',              # Channel ID
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            if pattern == r'@([a-zA-Z0-9_]+)':
                return '@' + match.group(1)
            elif pattern == r't\.me/([a-zA-Z0-9_]+)':
                return '@' + match.group(1)
            else:
                return match.group(1)
    
    return None
