from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import ContextTypes
from database import Post, PostSchedule, Channel, PostChannel, ScheduledJob
from config import ADMIN_ID, MAX_POSTS, MAX_CHANNELS_PER_POST, TIMEZONE
import re
import logging
import asyncio
import pytz
from datetime import datetime

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

def get_cuba_time():
    """Obtiene la hora actual de Cuba"""
    cuba_tz = pytz.timezone(TIMEZONE)
    return datetime.now(cuba_tz)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Si es administrador, mostrar panel de admin
    if user_id == ADMIN_ID:
        await start_admin_panel(update, context)
    else:
        # Si es usuario normal, mostrar mensaje de bienvenida
        await start_user_welcome(update, context)

async def start_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Panel de administración para el admin"""
    keyboard = [
        [InlineKeyboardButton("📋 Mis Posts", callback_data="list_posts")],
        [InlineKeyboardButton("➕ Crear Post", callback_data="create_post")],
        [InlineKeyboardButton("📺 Gestionar Canales", callback_data="manage_channels")],
        [InlineKeyboardButton("📊 Estadísticas", callback_data="statistics")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    cuba_time = get_cuba_time()
    
    message_text = (
        "🤖 **Bienvenido al Auto Post Bot**\n\n"
        f"🕐 **Hora actual (Cuba):** {cuba_time.strftime('%H:%M:%S')}\n"
        f"📅 **Fecha:** {cuba_time.strftime('%d/%m/%Y')}\n\n"
        "Selecciona una opción:"
    )
    
    if update.message:
        await update.message.reply_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')
    elif update.callback_query:
        await update.callback_query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')

async def start_user_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mensaje de bienvenida para usuarios no administradores"""
    user = update.effective_user
    username = user.username if user.username else user.first_name
    
    # Botón de beneficios
    keyboard = [
        [InlineKeyboardButton("🎁 Beneficios del Bot", callback_data="show_benefits")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Mensaje con enlaces incrustados
    message_text = (
        f"Bienvenido **{username}** al bot de Publicidad de las listas "
        f"[𝗥𝗲𝗱ᴬᴵ](https://t.me/listredai) y "
        f"[𝗥𝗲𝗱ᴬᴵ 𝗫𝗫𝗫](https://t.me/listredaixxx) "
        f"para añadir su canal a la lista o Alquilar el bot para su propia Lista "
        f"consulte con mi Propietario: @osvaldo20032"
    )
    
    await update.message.reply_text(
        message_text, 
        reply_markup=reply_markup, 
        parse_mode='Markdown',
        disable_web_page_preview=False
    )

async def show_benefits(query):
    """Mostrar los beneficios del bot"""
    benefits_text = (
        "🎁 **Beneficios de ser Propietario del Bot**\n\n"
        
        "**🤖 Para el Propietario del Bot:**\n"
        "• ✅ **Automatización Total** - Publicación automática 24/7\n"
        "• ⏰ **Programación Flexible** - Configura horarios específicos\n"
        "• 📺 **Gestión de Múltiples Canales** - Hasta 90 canales por post\n"
        "• 🗑️ **Eliminación Automática** - Control total del contenido\n"
        "• 📊 **Estadísticas Detalladas** - Monitoreo en tiempo real\n"
        "• 🎯 **Personalización Completa** - Adapta el bot a tus necesidades\n"
        "• 💰 **Monetización** - Genera ingresos con tu lista de canales\n"
        "• 🔧 **Soporte Técnico** - Asistencia completa del desarrollador\n\n"
        
        "**📺 Beneficios para Canales en las Listas:**\n"
        "• 🚀 **Mayor Visibilidad** - Exposición a miles de usuarios\n"
        "• 👥 **Crecimiento de Suscriptores** - Aumento orgánico de miembros\n"
        "• 🎯 **Audiencia Segmentada** - Usuarios interesados en tu nicho\n"
        "• 📈 **Promoción Cruzada** - Intercambio de audiencias\n"
        "• 🆓 **Publicidad Gratuita** - Promoción sin costo adicional\n"
        "• 🤝 **Networking** - Conexión con otros administradores\n"
        "• ⭐ **Credibilidad** - Respaldo de una lista reconocida\n\n"
        
        "**🎁 Beneficios Especiales:**\n"
        "• 🔥 **Contenido Exclusivo** - Acceso a material premium\n"
        "• 💎 **Prioridad en Promociones** - Destaque especial\n"
        "• 📱 **Multi-plataforma** - Promoción en diferentes redes\n"
        "• 🎪 **Eventos Especiales** - Participación en promociones masivas\n\n"
        
        "💬 **¿Interesado?** Contacta con @osvaldo20032\n"
        "🚀 **¡Únete ahora y haz crecer tu canal!**"
    )
    
    keyboard = [
        [InlineKeyboardButton("📞 Contactar Propietario", url="https://t.me/osvaldo20032")],
        [InlineKeyboardButton("🔙 Volver al Inicio", callback_data="back_to_start")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        benefits_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def back_to_start_user(query, context):
    """Volver al mensaje inicial para usuarios"""
    user = query.from_user
    username = user.username if user.username else user.first_name
    
    keyboard = [
        [InlineKeyboardButton("🎁 Beneficios del Bot", callback_data="show_benefits")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = (
        f"Bienvenido **{username}** al bot de Publicidad de las listas "
        f"[𝗥𝗲𝗱ᴬᴵ](https://t.me/listredai) y "
        f"[𝗥𝗲𝗱ᴬᴵ 𝗫𝗫𝗫](https://t.me/listredaixxx) "
        f"para añadir su canal a la lista o Alquilar el bot para su propia Lista "
        f"consulte con mi Propietario: @osvaldo20032"
    )
    
    await query.edit_message_text(
        message_text,
        reply_markup=reply_markup,
        parse_mode='Markdown',
        disable_web_page_preview=False
    )

# Modifica la función handle_callback para incluir los nuevos callbacks
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = update.effective_user.id
    
    # Callbacks para usuarios no administradores
    if data == "show_benefits":
        await show_benefits(query)
        return
    elif data == "back_to_start":
        await back_to_start_user(query, context)
        return
    
    # Verificar si es administrador para el resto de callbacks
    if user_id != ADMIN_ID:
        await query.answer("❌ No tienes permisos de administrador.", show_alert=True)
        return
    
    # Navegación principal (solo para admin)
    if data == "back_main":
        await start_admin_panel(update, context)
    elif data == "list_posts":
        await list_posts(query)
    elif data == "create_post":
        await create_post_prompt(query, context)
    elif data == "manage_channels":
        await manage_channels_menu(query)
    elif data == "statistics":
        await show_statistics(query)
    
    # Resto de las funciones existentes...
    # (mantén todo el código existente de handle_callback)
    
    # Acciones de posts específicos
    elif data.startswith("post_"):
        await handle_post_action(query, data)
    elif data.startswith("configure_schedule_"):
        post_id = data.split('_')[2]
        await configure_schedule_menu(query, post_id)
    elif data.startswith("configure_channels_"):
        post_id = data.split('_')[2]
        await configure_channels_menu(query, context, post_id)
    elif data.startswith("delete_post_"):
        post_id = data.split('_')[2]
        await confirm_delete_post(query, post_id)
    elif data.startswith("confirm_delete_"):
        post_id = data.split('_')[2]
        await delete_post(query, post_id)
    
    # Configuración de horarios
    elif data.startswith("set_time_"):
        post_id = data.split('_')[2]
        await prompt_set_time(query, context, post_id)
    elif data.startswith("set_delete_"):
        post_id = data.split('_')[2]
        await prompt_set_delete_hours(query, context, post_id)
    elif data.startswith("set_days_"):
        post_id = data.split('_')[2]
        await configure_days_menu(query, context, post_id)
    elif data.startswith("toggle_day_"):
        parts = data.split('_')
        post_id, day_num = parts[2], int(parts[3])
        await toggle_day(query, context, post_id, day_num)
    elif data.startswith("save_days_"):
        post_id = data.split('_')[2]
        await save_days(query, context, post_id)
    
    # Nuevas funciones
    elif data.startswith("toggle_pin_"):
        post_id = data.split('_')[2]
        await toggle_pin_message(query, context, post_id)
    elif data.startswith("toggle_forward_"):
        post_id = data.split('_')[2]
        await toggle_forward_original(query, context, post_id)
    elif data.startswith("send_now_"):
        post_id = data.split('_')[2]
        await send_post_manually(query, context, post_id)
    elif data.startswith("confirm_send_"):
        post_id = data.split('_')[2]
        await confirm_manual_send(query, context, post_id)
    elif data.startswith("preview_"):
        post_id = data.split('_')[1]
        await preview_post(query, context, post_id)
    elif data.startswith("send_preview_"):
        post_id = data.split('_')[2]
        await send_preview_to_admin(query, context, post_id)
    
    # Gestión de canales
    elif data == "add_channel":
        await prompt_add_channel(query, context)
    elif data == "add_channels_bulk":
        await prompt_add_channels_bulk(query, context)
    elif data == "remove_channel":
        await show_remove_channel_menu(query)
    elif data == "list_channels":
        await show_channels_list(query)
    elif data.startswith("remove_channel_"):
        channel_id = data.split('_')[2]
        await remove_channel(query, channel_id)
    
    # Asignación de canales a posts
    elif data.startswith("toggle_channel_"):
        parts = data.split('_')
        post_id, channel_id = parts[2], parts[3]
        await toggle_channel_assignment(query, context, post_id, channel_id)
    elif data.startswith("save_assignments_"):
        post_id = data.split('_')[2]
        await save_channel_assignments(query, context, post_id)

async def list_posts(query):
    posts = Post.find_active()
    
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
                callback_data=f"post_{str(post._id)}"
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
    post_id = data.split('_')[1]
    post = Post.find_by_id(post_id)
    
    if not post:
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="list_posts")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("❌ Post no encontrado.", reply_markup=reply_markup)
        return
    
    schedule = PostSchedule.find_by_post_id(post_id)
    assigned_channels = PostChannel.count_by_post_id(post_id)
    
    # Información del horario
    schedule_info = "No configurado"
    if schedule:
        days_map = {1: "L", 2: "M", 3: "X", 4: "J", 5: "V", 6: "S", 7: "D"}
        current_days = [int(d) for d in schedule.days_of_week.split(',')]
        days_display = "".join([days_map[d] for d in current_days])
        schedule_info = f"{schedule.send_time} ({days_display}) - Eliminar: {schedule.delete_after_hours}h"
    
    keyboard = [
        [InlineKeyboardButton("⏰ Configurar Horario", callback_data=f"configure_schedule_{post_id}")],
        [InlineKeyboardButton("📺 Asignar Canales", callback_data=f"configure_channels_{post_id}")],
        [InlineKeyboardButton("👀 Vista Previa", callback_data=f"preview_{post_id}"),
         InlineKeyboardButton("📤 Enviar Ahora", callback_data=f"send_now_{post_id}")],
        [InlineKeyboardButton("🗑️ Eliminar Post", callback_data=f"delete_post_{post_id}")],
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
    
    keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="back_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📤 **Para crear un post:**\n\n"
        "1. Ve al canal fuente\n"
        "2. **Reenvía** el mensaje al bot\n"
        "3. El bot detectará automáticamente el contenido\n"
        "4. Podrás asignarle un nombre personalizado\n\n"
        "**Tipos soportados:**\n"
        "• Texto, Fotos, Videos\n"
        "• Audio, Documentos, GIFs\n"
        "• Stickers, Mensajes de voz\n\n"
        "⚠️ **Importante:** Usa 'Reenviar', no copiar",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def handle_post_creation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    message = update.message

    # Verificar si está en el estado correcto
    if context.user_data.get('state') != 'waiting_for_post':
        return

    try:
        post_count = Post.count_active()

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

        if message.forward_from_chat:
            source_channel = str(message.forward_from_chat.id)
            source_message_id = message.forward_from_message_id
        else:
            source_channel = str(message.chat.id)
            source_message_id = message.message_id

        # Guardar información temporalmente para solicitar nombre
        context.user_data['temp_post'] = {
            'source_channel': source_channel,
            'source_message_id': source_message_id,
            'content_type': content_type,
            'content_text': text or "",
            'file_id': file_id
        }
        
        # Cambiar estado para esperar nombre
        context.user_data['state'] = 'waiting_post_name'

        # Sugerir nombre por defecto
        default_name = f"Post {post_count + 1}"
        if text and len(text) > 5:
            # Tomar las primeras palabras del texto
            words = text.split()[:3]
            default_name = " ".join(words)
            if len(default_name) > 25:
                default_name = default_name[:25] + "..."

        keyboard = [[InlineKeyboardButton("🔙 Cancelar", callback_data="back_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await message.reply_text(
            f"✅ **Contenido detectado correctamente!**\n\n"
            f"**Tipo:** {content_type.title()}\n"
            f"**Fuente:** `{source_channel}`\n\n"
            f"📝 **Ahora envía un nombre para este post:**\n"
            f"Ejemplo: `{default_name}`\n\n"
            f"El nombre debe tener entre 3 y 50 caracteres.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    except Exception as e:
        logger.error(f"Error creating post: {e}")
        await message.reply_text(f"❌ Error al procesar el contenido: {str(e)}")

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
    post = Post.find_by_id(post_id)
    schedule = PostSchedule.find_by_post_id(post_id)
    
    if not post or not schedule:
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="list_posts")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("❌ Post o horario no encontrado.", reply_markup=reply_markup)
        return
    
    days_map = {1: "Lun", 2: "Mar", 3: "Mié", 4: "Jue", 5: "Vie", 6: "Sáb", 7: "Dom"}
    current_days = [int(d) for d in schedule.days_of_week.split(',')]
    days_display = ", ".join([days_map[d] for d in current_days])
    
    pin_status = "✅" if schedule.pin_message else "❌"
    forward_status = "✅" if schedule.forward_original else "❌"
    
    # Obtener hora actual de Cuba
    cuba_time = get_cuba_time()
    current_time = cuba_time.strftime('%H:%M:%S')
    current_date = cuba_time.strftime('%d/%m/%Y')
    
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
        f"🕐 **Hora actual (Cuba):** {current_time}\n"
        f"📅 **Fecha:** {current_date}\n\n"
        f"Selecciona qué configurar:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def toggle_pin_message(query, context: ContextTypes.DEFAULT_TYPE, post_id):
    try:
        schedule = PostSchedule.find_by_post_id(post_id)
        if schedule:
            schedule.pin_message = not schedule.pin_message
            schedule.save()
            
            status = "activado" if schedule.pin_message else "desactivado"
            await query.answer(f"✅ Fijar mensaje {status}")
            await configure_schedule_menu(query, post_id)
        else:
            keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="list_posts")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("❌ Horario no encontrado.", reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Error toggling pin: {e}")
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="list_posts")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"❌ Error: {str(e)}", reply_markup=reply_markup)

async def toggle_forward_original(query, context: ContextTypes.DEFAULT_TYPE, post_id):
    try:
        schedule = PostSchedule.find_by_post_id(post_id)
        if schedule:
            schedule.forward_original = not schedule.forward_original
            schedule.save()
            
            status = "activado" if schedule.forward_original else "desactivado"
            await query.answer(f"✅ Reenvío original {status}")
            await configure_schedule_menu(query, post_id)
        else:
            keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="list_posts")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("❌ Horario no encontrado.", reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Error toggling forward: {e}")
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="list_posts")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"❌ Error: {str(e)}", reply_markup=reply_markup)

async def prompt_set_time(query, context: ContextTypes.DEFAULT_TYPE, post_id):
    context.user_data['state'] = 'waiting_time'
    context.user_data['post_id'] = post_id
    
    # Obtener hora actual de Cuba
    cuba_time = get_cuba_time()
    current_time = cuba_time.strftime('%H:%M')
    
    keyboard = [[InlineKeyboardButton("🔙 Cancelar", callback_data=f"configure_schedule_{post_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"🕐 **Configurar Hora de Envío**\n\n"
        f"🇨🇺 **Hora actual (Cuba):** {current_time}\n\n"
        f"Envía la hora en formato **HH:MM**\n"
        f"Ejemplos: `09:30`, `14:00`, `20:15`\n\n"
        f"⏰ La hora se basa en el horario de Cuba",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def prompt_set_delete_hours(query, context: ContextTypes.DEFAULT_TYPE, post_id):
    context.user_data['state'] = 'waiting_delete_hours'
    context.user_data['post_id'] = post_id
    
    keyboard = [[InlineKeyboardButton("🔙 Cancelar", callback_data=f"configure_schedule_{post_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "⏰ **Horas para Eliminar**\n\n"
        "Envía el número de horas (1-48)\n"
        "Ejemplos: `1`, `6`, `24`\n\n"
        "Envía `0` para no eliminar automáticamente",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def configure_days_menu(query, context: ContextTypes.DEFAULT_TYPE, post_id):
    schedule = PostSchedule.find_by_post_id(post_id)
    
    if not schedule:
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="list_posts")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("❌ Horario no encontrado.", reply_markup=reply_markup)
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
    
    try:
        schedule = PostSchedule.find_by_post_id(post_id)
        if schedule:
            schedule.days_of_week = ','.join(map(str, sorted(selected_days)))
            schedule.save()
            
            # Reprogramar en el scheduler
            from scheduler import reschedule_post_job
            reschedule_post_job(query.bot, post_id)
            
            await query.answer("✅ Días guardados correctamente")
            context.user_data.pop('selected_days', None)
            context.user_data.pop('configuring_post_id', None)
            
            await configure_schedule_menu(query, post_id)
        else:
            keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="list_posts")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("❌ Horario no encontrado.", reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Error saving days: {e}")
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="list_posts")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"❌ Error al guardar: {str(e)}", reply_markup=reply_markup)

# --- ENVÍO MANUAL Y VISTA PREVIA ---
async def send_post_manually(query, context: ContextTypes.DEFAULT_TYPE, post_id):
    """Enviar post manualmente a todos los canales asignados"""
    try:
        post = Post.find_by_id(post_id)
        if not post:
            keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="list_posts")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("❌ Post no encontrado.", reply_markup=reply_markup)
            return
        
        post_channels = PostChannel.find_by_post_id(post_id)
        if not post_channels:
            keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data=f"post_{post_id}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("❌ No hay canales asignados a este post.", reply_markup=reply_markup)
            return
        
        schedule = PostSchedule.find_by_post_id(post_id)
        
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
        
    except Exception as e:
        logger.error(f"Error in send_post_manually: {e}")
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="list_posts")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"❌ Error: {str(e)}", reply_markup=reply_markup)

async def confirm_manual_send(query, context: ContextTypes.DEFAULT_TYPE, post_id):
    """Confirmar y ejecutar envío manual"""
    await query.edit_message_text("📤 Enviando post...")
    
    try:
        post = Post.find_by_id(post_id)
        post_channels = PostChannel.find_by_post_id(post_id)
        schedule = PostSchedule.find_by_post_id(post_id)
        
        if not post or not post_channels:
            keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="list_posts")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("❌ Error: Post o canales no encontrados.", reply_markup=reply_markup)
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
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="list_posts")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"❌ Error durante el envío: {str(e)}", reply_markup=reply_markup)

async def preview_post(query, context: ContextTypes.DEFAULT_TYPE, post_id):
    """Mostrar vista previa del post"""
    try:
        post = Post.find_by_id(post_id)
        if not post:
            keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="list_posts")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("❌ Post no encontrado.", reply_markup=reply_markup)
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
        
    except Exception as e:
        logger.error(f"Error in preview_post: {e}")
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="list_posts")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"❌ Error: {str(e)}", reply_markup=reply_markup)

async def send_preview_to_admin(query, context: ContextTypes.DEFAULT_TYPE, post_id):
    """Enviar vista previa real del contenido"""
    try:
        post = Post.find_by_id(post_id)
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
            
    except Exception as e:
        logger.error(f"Error in send_preview_to_admin: {e}")
        await query.answer(f"❌ Error: {str(e)}")

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
        [InlineKeyboardButton("📝 Añadir Canales en Masa", callback_data="add_channels_bulk")],
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
    """Verifica si el bot es administrador del canal y tiene los permisos requeridos"""
    try:
        chat_member = await bot.get_chat_member(channel_id, bot.id)
        
        if chat_member.status not in ['administrator', 'creator']:
            return False, "El bot no es administrador en el canal"
        
        # Verificar permisos específicos
        if chat_member.status == 'administrator':
            if not chat_member.can_post_messages:
                return False, "El bot no tiene permisos para enviar mensajes"
            if not chat_member.can_edit_messages:
                return False, "El bot no tiene permisos para editar mensajes"
            if not chat_member.can_delete_messages:
                return False, "El bot no tiene permisos para eliminar mensajes"
        
        return True, "Permisos correctos"
        
    except Exception as e:
        return False, f"Error verificando permisos: {str(e)}"

async def prompt_add_channel(query, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['state'] = 'waiting_channel'
    
    keyboard = [[InlineKeyboardButton("🔙 Cancelar", callback_data="manage_channels")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "➕ **Añadir Canal Individual**\n\n"
        "Envía el canal en uno de estos formatos:\n"
        "• `@nombre_canal`\n"
        "• `https://t.me/nombre_canal`\n"
        "• `-1001234567890` (ID)\n\n"
        "⚠️ El bot debe ser admin en el canal",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def prompt_add_channels_bulk(query, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['state'] = 'waiting_channels_bulk'
    
    keyboard = [[InlineKeyboardButton("🔙 Cancelar", callback_data="manage_channels")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📝 **Añadir Canales en Masa**\n\n"
        "Envía múltiples canales, uno por línea:\n\n"
        "**Ejemplo:**\n"
        "`https://t.me/canal1`\n"
        "`@canal2`\n"
        "`https://t.me/canal3`\n"
        "`-1001234567890`\n\n"
        "⚠️ **Importante:**\n"
        "• Un canal por línea\n"
        "• El bot debe ser admin en todos\n"
        "• Máximo 20 canales por vez",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def show_channels_list(query):
    channels = Channel.find_all()
    
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
    channels = Channel.find_all()
    
    if not channels:
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="manage_channels")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("📭 No hay canales para eliminar.", reply_markup=reply_markup)
        return
    
    keyboard = []
    for channel in channels:
        name = channel.channel_name or channel.channel_username or channel.channel_id
        keyboard.append([
            InlineKeyboardButton(f"🗑️ {name}", callback_data=f"remove_channel_{str(channel._id)}")
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="manage_channels")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "➖ **Eliminar Canal**\n\nSelecciona el canal:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def remove_channel(query, channel_id):
    try:
        # Buscar canal por ObjectId
        from bson import ObjectId
        from database import db
        
        channel_doc = db.channels.find_one({'_id': ObjectId(channel_id)})
        if channel_doc:
            channel = Channel.from_dict(channel_doc)
            if channel.delete():
                await query.answer("✅ Canal eliminado correctamente")
                await manage_channels_menu(query)
            else:
                keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="manage_channels")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text("❌ Error al eliminar el canal.", reply_markup=reply_markup)
        else:
            keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="manage_channels")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("❌ Canal no encontrado.", reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Error removing channel: {e}")
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="manage_channels")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"❌ Error: {str(e)}", reply_markup=reply_markup)

# --- ASIGNACIÓN DE CANALES A POSTS ---
async def configure_channels_menu(query, context: ContextTypes.DEFAULT_TYPE, post_id):
    all_channels = Channel.find_all()
    if not all_channels:
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data=f"post_{post_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "❌ No hay canales disponibles.\nPrimero añade canales.",
            reply_markup=reply_markup
        )
        return
    
    # Obtener canales asignados actualmente
    assigned = PostChannel.find_by_post_id(post_id)
    assigned_ids = [pc.channel_id for pc in assigned]
    
    # Guardar selección actual
    context.user_data['channel_assignments'] = assigned_ids.copy()
    context.user_data['assigning_post_id'] = post_id
    
    await update_channels_menu(query, context, post_id)

async def update_channels_menu(query, context: ContextTypes.DEFAULT_TYPE, post_id):
    all_channels = Channel.find_all()
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
    
    try:
        # Eliminar asignaciones existentes
        PostChannel.delete_by_post_id(post_id)
        
        # Añadir nuevas asignaciones
        for channel_id in selected_channels:
            post_channel = PostChannel(post_id=post_id, channel_id=channel_id)
            post_channel.save()
        
        context.user_data.pop('channel_assignments', None)
        context.user_data.pop('assigning_post_id', None)
        
        await query.answer(f"✅ {len(selected_channels)} canales asignados")
        await handle_post_action(query, f"post_{post_id}")
        
    except Exception as e:
        logger.error(f"Error saving assignments: {e}")
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="list_posts")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"❌ Error: {str(e)}", reply_markup=reply_markup)

# --- ELIMINAR POSTS ---
async def confirm_delete_post(query, post_id):
    post = Post.find_by_id(post_id)
    
    if not post:
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="list_posts")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("❌ Post no encontrado.", reply_markup=reply_markup)
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
    try:
        post = Post.find_by_id(post_id)
        if post:
            if post.delete():
                # Eliminar trabajos del scheduler
                from scheduler import remove_post_jobs
                remove_post_jobs(post_id)
                
                await query.answer("✅ Post eliminado")
                await list_posts(query)
            else:
                keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="list_posts")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text("❌ Error al eliminar el post.", reply_markup=reply_markup)
        else:
            keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="list_posts")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("❌ Post no encontrado.", reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Error deleting post: {e}")
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="list_posts")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"❌ Error: {str(e)}", reply_markup=reply_markup)

# --- ESTADÍSTICAS ---
async def show_statistics(query):
    total_posts = Post.count_active()
    total_channels = Channel.count_all()
    total_schedules = PostSchedule.count_enabled()
    
    keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="back_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    status = "🟢 Operativo" if total_posts > 0 else "🟡 Sin posts"
    cuba_time = get_cuba_time()
    
    await query.edit_message_text(
        f"📊 **Estadísticas del Bot**\n\n"
        f"🕐 **Hora (Cuba):** {cuba_time.strftime('%H:%M:%S')}\n"
        f"📅 **Fecha:** {cuba_time.strftime('%d/%m/%Y')}\n\n"
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
    
    if state == 'waiting_post_name':
        await handle_post_name_input(update, context, text)
    elif state == 'waiting_time':
        await handle_time_input(update, context, text)
    elif state == 'waiting_delete_hours':
        await handle_delete_hours_input(update, context, text)
    elif state == 'waiting_channel':
        await handle_channel_input(update, context, text)
    elif state == 'waiting_channels_bulk':
        await handle_channels_bulk_input(update, context, text)

async def handle_post_name_input(update, context, text):
    """Manejar entrada del nombre del post"""
    if len(text) < 3 or len(text) > 50:
        await update.message.reply_text("❌ El nombre debe tener entre 3 y 50 caracteres.")
        return
    
    try:
        temp_post = context.user_data.get('temp_post')
        if not temp_post:
            await update.message.reply_text("❌ Error: No se encontró información del post.")
            return
        
        # Crear post con el nombre personalizado
        post = Post(
            name=text,
            source_channel=temp_post['source_channel'],
            source_message_id=temp_post['source_message_id'],
            content_type=temp_post['content_type'],
            content_text=temp_post['content_text'],
            file_id=temp_post['file_id']
        )

        if not post.save():
            await update.message.reply_text("❌ Error al crear el post.")
            return

        # Crear horario por defecto
        schedule = PostSchedule(
            post_id=str(post._id),
            send_time="09:00",
            delete_after_hours=24,
            days_of_week="1,2,3,4,5,6,7",
            pin_message=False,
            forward_original=True
        )
        schedule.save()

        # Limpiar datos temporales
        context.user_data.pop('state', None)
        context.user_data.pop('temp_post', None)

        # Crear botones de acción rápida
        keyboard = [
            [InlineKeyboardButton("⚙️ Configurar", callback_data=f"post_{str(post._id)}")],
            [InlineKeyboardButton("📺 Asignar Canales", callback_data=f"configure_channels_{str(post._id)}")],
            [InlineKeyboardButton("📤 Enviar Ahora", callback_data=f"send_now_{str(post._id)}")],
            [InlineKeyboardButton("🏠 Menú Principal", callback_data="back_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"✅ **Post '{text}' creado exitosamente!**\n\n"
            f"**ID:** {str(post._id)}\n"
            f"**Tipo:** {post.content_type.title()}\n"
            f"**Fuente:** `{temp_post['source_channel']}`\n\n"
            f"¿Qué quieres hacer ahora?",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    except Exception as e:
        logger.error(f"Error creating post with name: {e}")
        await update.message.reply_text(f"❌ Error al crear el post: {str(e)}")

async def handle_time_input(update, context, text):
    if not re.match(r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$', text):
        await update.message.reply_text("❌ Formato inválido. Usa HH:MM (ej: 09:30)")
        return
    
    post_id = context.user_data.get('post_id')
    
    try:
        schedule = PostSchedule.find_by_post_id(post_id)
        if schedule:
            schedule.send_time = text
            schedule.save()
            
            from scheduler import reschedule_post_job
            reschedule_post_job(context.bot, post_id)
            
            await update.message.reply_text(f"✅ Hora configurada: {text} (Horario de Cuba)")
            context.user_data.pop('state', None)
            context.user_data.pop('post_id', None)
        else:
            await update.message.reply_text("❌ Horario no encontrado.")
    except Exception as e:
        logger.error(f"Error setting time: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")

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
    
    try:
        schedule = PostSchedule.find_by_post_id(post_id)
        if schedule:
            schedule.delete_after_hours = hours
            schedule.save()
            
            await update.message.reply_text(f"✅ Configurado: eliminar después de {hours} horas")
            context.user_data.pop('state', None)
            context.user_data.pop('post_id', None)
        else:
            await update.message.reply_text("❌ Horario no encontrado.")
    except Exception as e:
        logger.error(f"Error setting delete hours: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def handle_channel_input(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
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

    try:
        # Verificar si ya existe
        existing = Channel.find_by_channel_id(channel_info)
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
                    f"   • Publicar mensajes\n"
                    f"   • Editar mensajes de otros\n"
                    f"   • Eliminar mensajes de otros\n"
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

        if not channel.save():
            await verification_msg.edit_text("❌ Error al guardar el canal")
            return

        # Enviar mensaje de confirmación al canal
        try:
            confirmation_message = await context.bot.send_message(
                chat_id=channel_id_final,
                text=f"✅ El bot ha sido añadido correctamente al canal: {channel_name or 'Sin nombre'}"
            )

            # Programar eliminación del mensaje de confirmación en 30 segundos
            await asyncio.sleep(30)
            try:
                await context.bot.delete_message(chat_id=channel_id_final, message_id=confirmation_message.message_id)
            except:
                pass
        except:
            pass

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
        logger.error(f"Error adding channel: {e}")
        await verification_msg.edit_text(f"❌ Error: {str(e)}")

async def handle_channels_bulk_input(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """Manejar entrada de canales en masa"""
    lines = text.strip().split('\n')
    
    if len(lines) > 20:
        await update.message.reply_text("❌ Máximo 20 canales por vez")
        return
    
    # Mensaje de progreso
    progress_msg = await update.message.reply_text("🔄 Procesando canales...")
    
    channels_to_add = []
    errors = []
    
    # Extraer información de cada línea
    for i, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue
            
        channel_info = extract_channel_info(line)
        if not channel_info:
            errors.append(f"Línea {i}: Formato inválido")
            continue
            
        # Verificar si ya existe
        existing = Channel.find_by_channel_id(channel_info)
        if existing:
            errors.append(f"Línea {i}: Canal ya registrado")
            continue
            
        channels_to_add.append((i, channel_info, line))
    
    if not channels_to_add:
        await progress_msg.edit_text("❌ No hay canales válidos para procesar")
        return
    
    # Procesar cada canal
    added_channels = []
    
    for line_num, channel_info, original_line in channels_to_add:
        try:
            await progress_msg.edit_text(f"🔍 Verificando canal {line_num}/{len(lines)}...")
            
            # Obtener información del canal
            chat = await context.bot.get_chat(channel_info)
            channel_id_final = str(chat.id)
            channel_name = chat.title
            channel_username = chat.username

            # Verificar permisos
            has_permissions, permission_msg = await verify_bot_permissions(context.bot, channel_id_final)
            
            if not has_permissions:
                errors.append(f"Línea {line_num}: {permission_msg}")
                continue

            # Crear canal
            channel = Channel(
                channel_id=channel_id_final,
                channel_name=channel_name,
                channel_username=channel_username
            )

            if channel.save():
                added_channels.append({
                    'line': line_num,
                    'name': channel_name or channel_username or channel_id_final,
                    'id': channel_id_final
                })
                
                # Enviar mensaje de confirmación (sin esperar)
                try:
                    confirmation_message = await context.bot.send_message(
                        chat_id=channel_id_final,
                        text=f"✅ Bot añadido correctamente"
                    )
                    # Programar eliminación en background
                    asyncio.create_task(delete_confirmation_message(context.bot, channel_id_final, confirmation_message.message_id))
                except:
                    pass
            else:
                errors.append(f"Línea {line_num}: Error al guardar")
                
        except Exception as e:
            errors.append(f"Línea {line_num}: {str(e)}")
    
    # Limpiar estado
    context.user_data.pop('state', None)
    
    # Mostrar resultado
    result_text = f"📊 **Resultado del Procesamiento**\n\n"
    result_text += f"✅ **Añadidos:** {len(added_channels)}\n"
    result_text += f"❌ **Errores:** {len(errors)}\n"
    result_text += f"📝 **Total procesados:** {len(lines)}\n\n"
    
    if added_channels:
        result_text += "**Canales añadidos:**\n"
        for channel in added_channels[:10]:  # Mostrar solo los primeros 10
            result_text += f"• {channel['name']}\n"
        if len(added_channels) > 10:
            result_text += f"• ... y {len(added_channels) - 10} más\n"
        result_text += "\n"
    
    if errors:
        result_text += "**Errores encontrados:**\n"
        for error in errors[:5]:  # Mostrar solo los primeros 5 errores
            result_text += f"• {error}\n"
        if len(errors) > 5:
            result_text += f"• ... y {len(errors) - 5} errores más\n"
    
    await progress_msg.edit_text(result_text, parse_mode='Markdown')

async def delete_confirmation_message(bot: Bot, channel_id: str, message_id: int):
    """Eliminar mensaje de confirmación después de 30 segundos"""
    await asyncio.sleep(30)
    try:
        await bot.delete_message(chat_id=channel_id, message_id=message_id)
    except:
        pass

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
