import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from config import BOT_TOKEN, ADMIN_ID
from handlers import (
    start, handle_callback, handle_post_creation, 
    handle_text_input, admin_only
)
from scheduler import start_scheduler
from health_server import health_server  # Nuevo import

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    # Iniciar servidor de salud ANTES que el bot
    health_server.start()
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # Handler para mensajes reenviados (crear posts)
    application.add_handler(MessageHandler(
        filters.FORWARDED & ~filters.COMMAND, 
        handle_post_creation
    ))
    
    # Handler para inputs de texto del usuario
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & ~filters.FORWARDED,
        handle_text_input
    ))
    
    # Iniciar scheduler
    start_scheduler(application)
    
    logger.info("🤖 Bot y Health Server iniciados correctamente...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
