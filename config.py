import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN', '8063509725:AAHsa32julaJ4fst2OWhgj7lkL_HdA5ALN4')
ADMIN_ID = int(os.getenv('ADMIN_ID', '1742433244'))

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///auto_post_bot.db')
TIMEZONE = os.getenv('TIMEZONE', 'UTC')

MAX_POSTS = 5
MAX_CHANNELS_PER_POST = 50
