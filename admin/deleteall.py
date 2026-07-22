import asyncio
from telegram import Update
from telegram.ext import ContextTypes

from database import get_all_movies, delete_all_movies

async def deleteall_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message

    reply = await msg.reply_text("Fetching all movies from the database... This may take a while.")
    
    movies = await get_all_movies()
    if not movies:
        await reply.edit_text("Database is already empty.")
        return

    await reply.edit_text(f"Found {len(movies)} movies. Starting deletion from Telegram group... (sleeping 1s per message to avoid ban)")

    deleted_count = 0
    for movie in movies:
        chat_id = movie["chat_id"]
        message_id = movie["message_id"]
        
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
            deleted_count += 1
            print(f"[-] Deleted message: {message_id}")
        except Exception as e:
            print(f"[!] Failed to delete message {message_id}: {e}")
            
        # VERY IMPORTANT: Rate limiting cooldown to prevent Telegram from banning the bot
        await asyncio.sleep(1.0)
        
    await reply.edit_text(f"Successfully deleted {deleted_count} messages from Telegram. Now wiping the database...")
    
    await delete_all_movies()
    
    await reply.edit_text(f"Database wiped! 🧹 Total {len(movies)} records deleted.")
