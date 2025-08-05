from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
    
    if context.user_data.get('state') != 'waiting_for_post':
        return
    
    message = update.message
    
    if not message.forward_origin:
        await message.reply_text("❌ Por favor reenvía un mensaje desde un canal.")
        return
    
    session = get_session()
    try:
        post_count = session.query(Post).filter_by(is_active=True).count()
        
        if post_count >= MAX_POSTS:
            await message.reply_text(f"❌ Máximo {MAX_POSTS} posts permitidos. Elimina uno existente primero.")
            return
        
        # Detectar tipo de contenido
        content_type, file_id, text = extract_content_info(message)
        
        if not content_type:
            await message.reply_text("❌ Tipo de contenido no soportado.")
            return
        
        # Obtener información de la fuente
        source_channel = None
        source_message_id = None
        
        if hasattr(message.forward_origin, 'chat'):
            source_channel = str(message.forward_origin.chat.id)
            source_message_id = message.forward_origin.message_id
        else:
            source_channel = str(message.chat.id)
            source_message_id = message.message_id
        
        # Crear post
        post = Post(
            name=f"Post {post_count + 1}",
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
            days_of_week="1,2,3,4,5,6,7"
        )
        session.add(schedule)
        session.commit()
        
        context.user_data.pop('state', None)
        
        await message.reply_text(
            f"✅ **Post creado exitosamente!**\n\n"
            f"**ID:** {post.id}\n"
            f"**Nombre:** {post.name}\n"
            f"**Tipo:** {content_type.title()}\n\n"
            f"Usa /start para configurar horarios y canales.",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error creating post: {e}")
        await message.reply_text(f"❌ Error al crear el post: {str(e)}")
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
    
    keyboard = [
        [InlineKeyboardButton(f"🕐 Hora: {schedule.send_time}", callback_data=f"set_time_{post_id}")],
        [InlineKeyboardButton(f"⏰ Eliminar después: {schedule.delete_after_hours}h", callback_data=f"set_delete_{post_id}")],
        [InlineKeyboardButton(f"📅 Días: {days_display}", callback_data=f"set_days_{post_id}")],
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
    
    session = get_session()
    try:
        # Verificar si ya existe
        existing = session.query(Channel).filter_by(channel_id=channel_info).first()
        if existing:
            await update.message.reply_text("❌ Este canal ya está registrado")
            return
        
        # Intentar obtener información del canal
        channel_name = None
        channel_username = None
        
        try:
            chat = await context.bot.get_chat(channel_info)
            channel_info = str(chat.id)
            channel_name = chat.title
            channel_username = chat.username
        except Exception as e:
            logger.warning(f"Could not get chat info for {channel_info}: {e}")
        
        # Crear canal
        channel = Channel(
            channel_id=channel_info,
            channel_name=channel_name,
            channel_username=channel_username
        )
        
        session.add(channel)
        session.commit()
        
        context.user_data.pop('state', None)
        
        await update.message.reply_text(f"✅ Canal añadido: `{channel_info}`", parse_mode='Markdown')
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error adding channel: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")
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
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "list_posts":
        await list_posts(query)
    elif data.startswith("post_"):
        await handle_post_action(query, data)
    elif data == "create_post":
        await create_post_prompt(query)
    elif data.startswith("configure_"):
        await configure_post(query, data)
    elif data == "manage_channels":
        await manage_channels(query)
    elif data.startswith("channel_"):
        await handle_channel_action(query, data)
    elif data == "statistics":
        await show_statistics(query)

async def list_posts(query):
    session = get_session()
    posts = session.query(Post).filter_by(is_active=True).all()
    session.close()
    
    if not posts:
        await query.edit_message_text("No hay posts activos.")
        return
    
    keyboard = []
    for post in posts:
        keyboard.append([
            InlineKeyboardButton(
                f"📄 {post.name} ({post.content_type})", 
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
    session.close()
    
    if not post:
        await query.edit_message_text("Post no encontrado.")
        return
    
    keyboard = [
        [InlineKeyboardButton("⚙️ Configurar Horario", callback_data=f"configure_schedule_{post_id}")],
        [InlineKeyboardButton("📺 Asignar Canales", callback_data=f"configure_channels_{post_id}")],
        [InlineKeyboardButton("🗑️ Eliminar Post", callback_data=f"delete_post_{post_id}")],
        [InlineKeyboardButton("🔙 Volver", callback_data="list_posts")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"**Post:** {post.name}\n"
        f"**Tipo:** {post.content_type}\n"
        f"**Canal Fuente:** {post.source_channel}\n"
        f"**ID Mensaje:** {post.source_message_id}",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def create_post_prompt(query):
    await query.edit_message_text(
        "📤 **Para crear un post:**\n\n"
        "1. Ve al canal fuente\n"
        "2. Reenvía el mensaje que quieres usar al bot\n"
        "3. El bot detectará automáticamente el contenido\n\n"
        "El mensaje puede ser texto, foto, video, audio o documento."
    )

async def handle_post_creation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    message = update.channel_post or update.message
    
    # Check if we already have 5 posts
    session = get_session()
    post_count = session.query(Post).filter_by(is_active=True).count()
    
    if post_count >= MAX_POSTS:
        await message.reply_text(f"❌ Máximo {MAX_POSTS} posts permitidos. Elimina uno existente primero.")
        session.close()
        return
    
    # Extract content info
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
    
    # Create post
    post = Post(
        name=f"Post {post_count + 1}",
        source_channel=str(message.chat.id),
        source_message_id=message.message_id,
        content_type=content_type,
        content_text=text or "",
        file_id=file_id
    )
    
    session.add(post)
    session.commit()
    
    # Create default schedule
    schedule = PostSchedule(
        post_id=post.id,
        send_time="09:00",
        delete_after_hours=24,
        days_of_week="1,2,3,4,5,6,7"
    )
    session.add(schedule)
    session.commit()
    session.close()
    
    await message.reply_text(
        f"✅ **Post creado exitosamente!**\n\n"
        f"**ID:** {post.id}\n"
        f"**Nombre:** {post.name}\n"
        f"**Tipo:** {content_type}\n\n"
        f"Ahora puedes configurar horarios y asignar canales.",
        parse_mode='Markdown'
    )

async def configure_post(query, data):
    post_id = int(data.split('_')[1])
    
    keyboard = [
        [InlineKeyboardButton("🕐 Hora de Envío", callback_data=f"set_time_{post_id}")],
        [InlineKeyboardButton("⏰ Horas para Eliminar", callback_data=f"set_delete_{post_id}")],
        [InlineKeyboardButton("📅 Días de Publicación", callback_data=f"set_days_{post_id}")],
        [InlineKeyboardButton("🔙 Volver", callback_data=f"post_{post_id}")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "⚙️ **Configuración del Post**\n\n"
        "Selecciona qué deseas configurar:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def manage_channels(query):
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

async def show_statistics(query):
    session = get_session()
    
    total_posts = session.query(Post).filter_by(is_active=True).count()
    total_channels = session.query(Channel).count()
    total_scheduled = session.query(PostSchedule).filter_by(is_enabled=True).count()
    
    session.close()
    
    await query.edit_message_text(
        f"📊 **Estadísticas del Bot**\n\n"
        f"**Posts Activos:** {total_posts}\n"
        f"**Canales Registrados:** {total_channels}\n"
        f"**Horarios Activos:** {total_scheduled}\n\n"
        f"**Límite de Posts:** {MAX_POSTS}",
        parse_mode='Markdown'
    )

