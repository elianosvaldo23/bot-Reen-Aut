import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN', '8063509725:AAHsa32julaJ4fst2OWhgj7lkL_HdA5ALN4')
ADMIN_ID = int(os.getenv('ADMIN_ID', '1742433244'))

# MongoDB Configuration
MONGODB_URL = os.getenv('MONGODB_URL', 'mongodb+srv://zoobot:zoobot@zoolbot.6avd6qf.mongodb.net/zoolbot?retryWrites=true&w=majority&appName=Zoolbot')
DATABASE_NAME = os.getenv('DATABASE_NAME', 'zoolbot')

TIMEZONE = os.getenv('TIMEZONE', 'UTC')

MAX_POSTS = 15
MAX_CHANNELS_PER_POST = 90
