import time
import logging

from bot_instance import bot
from database import get_all_movies, delete_all_movies
from utils import db_retry

logger = logging.getLogger(__name__)


def deleteall_cmd(message):
    chat_id = message.chat.id
    reply = bot.reply_to(message, "Fetching all movies from the database... This may take a while.")

    movies = get_all_movies()
    if not movies:
        bot.edit_message_text(
            text="Database is already empty.",
            chat_id=chat_id,
            message_id=reply.message_id,
        )
        return

    bot.edit_message_text(
        text=(
            f"Found {len(movies)} movies. "
            f"Starting deletion from Telegram group... (sleeping 1s per message to avoid ban)"
        ),
        chat_id=chat_id,
        message_id=reply.message_id,
    )

    deleted_count = 0
    for movie in movies:
        movie_chat_id = movie["chat_id"]
        movie_message_id = movie["message_id"]

        try:
            bot.delete_message(chat_id=movie_chat_id, message_id=movie_message_id)
            deleted_count += 1
            logger.info(f"[-] Deleted message: {movie_message_id}")
        except Exception as e:
            logger.warning(f"[!] Failed to delete message {movie_message_id}: {e}")

        # Rate-limit guard: avoid Telegram banning the bot for bulk deletions.
        time.sleep(1.0)

    bot.edit_message_text(
        text=f"Successfully deleted {deleted_count} messages from Telegram. Now wiping the database...",
        chat_id=chat_id,
        message_id=reply.message_id,
    )

    try:
        db_retry(delete_all_movies)
        bot.edit_message_text(
            text=f"Database wiped! 🧹 Total {len(movies)} records deleted.",
            chat_id=chat_id,
            message_id=reply.message_id,
        )
    except Exception as e:
        # All Telegram messages are already deleted. The DB still has records.
        # Running /deleteall again is safe: Telegram will return "not found" for
        # each message (ignored), and the DB wipe will be retried.
        logger.critical(
            f"[INCONSISTENCY] DB wipe failed after all Telegram deletes completed. "
            f"{len(movies)} ghost records remain. Run /deleteall again to retry. Error: {e}"
        )
        bot.edit_message_text(
            text="⚠️ Telegram messages deleted but database wipe failed. Run /deleteall again to retry.",
            chat_id=chat_id,
            message_id=reply.message_id,
        )
