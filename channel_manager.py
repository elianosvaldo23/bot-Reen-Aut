from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import get_session, Channel, PostChannel, Post
import re

class ChannelManager:
    def __init__(self):
        self.session = get_session()
    
    def add_channel(self, channel_id: str, channel_name: str = None, channel_username: str = None):
        """Add a new channel to the database"""
        try:
            channel = Channel(
                channel_id=channel_id,
                channel_name=channel_name,
                channel_username=channel_username
            )
            self.session.add(channel)
            self.session.commit()
            return True
        except Exception as e:
            self.session.rollback()
            return False
    
    def remove_channel(self, channel_id: str):
        """Remove a channel from the database"""
        try:
            channel = self.session.query(Channel).filter_by(channel_id=channel_id).first()
            if channel:
                # Remove from all post assignments
                self.session.query(PostChannel).filter_by(channel_id=channel_id).delete()
                self.session.delete(channel)
                self.session.commit()
                return True
            return False
        except Exception as e:
            self.session.rollback()
            return False
    
    def get_all_channels(self):
        """Get all registered channels"""
        return self.session.query(Channel).all()
    
    def get_channels_for_post(self, post_id: int):
        """Get all channels assigned to a specific post"""
        post_channels = self.session.query(PostChannel).filter_by(post_id=post_id).all()
        channel_ids = [pc.channel_id for pc in post_channels]
        return self.session.query(Channel).filter(Channel.channel_id.in_(channel_ids)).all()
    
    def assign_channels_to_post(self, post_id: int, channel_ids: list):
        """Assign multiple channels to a post"""
        try:
            # Remove existing assignments
            self.session.query(PostChannel).filter_by(post_id=post_id).delete()
            
            # Add new assignments
            for channel_id in channel_ids:
                post_channel = PostChannel(
                    post_id=post_id,
                    channel_id=channel_id
                )
                self.session.add(post_channel)
            
            self.session.commit()
            return True
        except Exception as e:
            self.session.rollback()
            return False
    
    def get_unassigned_channels(self, post_id: int):
        """Get channels not assigned to a specific post"""
        assigned = self.session.query(PostChannel.channel_id).filter_by(post_id=post_id).subquery()
        return self.session.query(Channel).filter(~Channel.channel_id.in_(assigned)).all()

def extract_channel_info(text):
    """Extract channel ID from text input"""
    # Handle different formats:
    # - @channelusername
    # - https://t.me/channelusername
    # - -1001234567890 (channel ID)
    
    patterns = [
        r'@([a-zA-Z0-9_]+)',  # @channelusername
        r't\.me/([a-zA-Z0-9_]+)',  # t.me/channelusername
        r'(-100\d+)',  # Channel ID
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    
    return None

async def handle_add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle adding channels via text input"""
    if update.effective_user.id != ADMIN_ID:
        return
    
    text = update.message.text
    channel_info = extract_channel_info(text)
    
    if not channel_info:
        await update.message.reply_text(
            "❌ Formato inválido. Por favor envía:\n"
            "- @nombre_del_canal\n"
            "- https://t.me/nombre_del_canal\n"
            "- ID del canal (-100...)"
        )
        return
    
    manager = ChannelManager()
    if manager.add_channel(channel_info):
        await update.message.reply_text(f"✅ Canal {channel_info} añadido exitosamente.")
    else:
        await update.message.reply_text("❌ Error al añadir el canal. Puede que ya exista.")

async def handle_remove_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle removing channels via text input"""
    if update.effective_user.id != ADMIN_ID:
        return
    
    text = update.message.text
    channel_info = extract_channel_info(text)
    
    if not channel_info:
        await update.message.reply_text(
            "❌ Formato inválido. Por favor envía el canal a eliminar."
        )
        return
    
    manager = ChannelManager()
    if manager.remove_channel(channel_info):
        await update.message.reply_text(f"✅ Canal {channel_info} eliminado exitosamente.")
    else:
        await update.message.reply_text("❌ Error al eliminar el canal o no existe.")

async def show_channel_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show list of all channels"""
    if update.effective_user.id != ADMIN_ID:
        return
    
    manager = ChannelManager()
    channels = manager.get_all_channels()
    
    if not channels:
        await update.message.reply_text("📭 No hay canales registrados.")
        return
    
    message = "📺 **Canales Registrados:**\n\n"
    for channel in channels:
        message += f"• `{channel.channel_id}`"
        if channel.channel_name:
            message += f" - {channel.channel_name}"
        if channel.channel_username:
            message += f" (@{channel.channel_username})"
        message += "\n"
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def assign_channels_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, post_id: int):
    """Show menu to assign channels to a post"""
    if update.effective_user.id != ADMIN_ID:
        return
    
    manager = ChannelManager()
    channels = manager.get_all_channels()
    
    if not channels:
        await update.message.reply_text("❌ No hay canales disponibles. Añade canales primero.")
        return
    
    keyboard = []
    assigned_channels = manager.get_channels_for_post(post_id)
    assigned_ids = [c.channel_id for c in assigned_channels]
    
    for channel in channels:
        status = "✅" if channel.channel_id in assigned_ids else "❌"
        keyboard.append([
            InlineKeyboardButton(
                f"{status} {channel.channel_name or channel.channel_id}",
                callback_data=f"toggle_channel_{post_id}_{channel.channel_id}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("✅ Guardar Asignaciones", callback_data=f"save_assignments_{post_id}")])
    keyboard.append([InlineKeyboardButton("🔙 Cancelar", callback_data=f"post_{post_id}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "📺 **Asignar Canales al Post**\n\n"
        "Selecciona los canales donde se enviará este post:",
        reply_markup=reply_markup
    )
