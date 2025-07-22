from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import get_session, Post, PostSchedule, Channel, PostChannel
from config import ADMIN_ID, MAX_POSTS
import re

def admin_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id != ADMIN_ID:
            await update.message.reply_text("❌ No tienes permisos de administrador.")
            return
        return await func(update, context)
    return wrapper

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Este bot es solo para administradores.")
        return
    
    keyboard = [
        [InlineKeyboardButton("📋 Mis Posts", callback_data="list_posts")],
        [InlineKeyboardButton("➕ Crear Post", callback_data="create_post")],
        [InlineKeyboardButton("⚙️ Configurar Post", callback_data="configure_post")],
        [InlineKeyboardButton("📺 Gestionar Canales", callback_data="manage_channels")],
        [InlineKeyboardButton("📊 Estadísticas", callback_data="statistics")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🤖 **Bienvenido al Auto Post Bot**\n\n"
        "Selecciona una opción:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
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
