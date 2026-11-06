import os
from dotenv import load_dotenv

load_dotenv()

config = {
    'bot_token':      os.environ['BOT_TOKEN'],
    'chat_id':        os.environ['CHAT_ID'],
    'website':        os.environ.get('WEBSITE', 'https://yourdomain.com/'),
    'admin_username': os.environ.get('ADMIN_USERNAME', 'DRIFT'),
    'admin_password': os.environ['ADMIN_PASSWORD'],
    'secret_key':     os.environ['SECRET_KEY'],
}