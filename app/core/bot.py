import telebot
from app.config import BOT_TOKEN

# Single TeleBot instance shared across all modules.
# Import this wherever you need to call Telegram API methods.
bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)
