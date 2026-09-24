import time
import logging

from app.core.bot import bot
from app.config import MOVIE_GROUP_ID
from app.core.database import (
    get_all_movies, update_movie, delete_all_movies, 
    get_movie_by_message_id, delete_movie
)
from app.services.tmdb import get_movie
from app.utils.extraction import extract_file_languages
from app.utils.formatting import build_caption
from app.utils.core_utils import db_retry, delete_after

logger = logging.getLogger(__name__)


@bot.message_handler(commands=['rebase'])
def handle_rebase(message):
    chat_id = message.chat.id
    reply = bot.reply_to(message, "Fetching all movies from the database for rebase...")

    movies = get_all_movies()
    if not movies:
        bot.edit_message_text(
            text="Database is empty. Nothing to rebase.",
            chat_id=chat_id,
            message_id=reply.message_id,
        )
        return

    bot.edit_message_text(
        text=f"Found {len(movies)} movies. Starting rebase... (sleeping 2s per movie to respect API limits)",
        chat_id=chat_id,
        message_id=reply.message_id,
    )

    updated_count = 0
    skipped_count = 0
    failed_count = 0

    for movie_record in movies:
        movie_chat_id = movie_record["chat_id"]
        movie_message_id = movie_record["message_id"]
        imdb_id = movie_record["imdb_id"]

        try:
            # 1. Fetch fresh metadata from TMDB.
            new_movie_data = get_movie(imdb_id)

            if not new_movie_data:
                logger.warning(
                    f"[~] TMDB returned no data for {imdb_id}. "
                    f"Skipping — existing record preserved."
                )
                skipped_count += 1
                time.sleep(2.0)
                continue

            title = new_movie_data["title"]
            alternate_title = new_movie_data.get("alternate_title")
            year = new_movie_data["year"]
            original_language = new_movie_data.get("original_language")
            
            file_name = movie_record.get("file_name")
            file_languages = extract_file_languages(file_name) if file_name else None

            caption = build_caption(title, alternate_title, year, original_language, file_languages, imdb_id)

            # 2. Update Telegram caption first.
            telegram_updated = False
            try:
                bot.edit_message_caption(
                    chat_id=movie_chat_id,
                    message_id=movie_message_id,
                    caption=caption,
                )
                telegram_updated = True
            except Exception as e:
                if "message is not modified" in str(e).lower():
                    telegram_updated = True
                else:
                    logger.warning(
                        f"[~] Telegram caption edit failed for message {movie_message_id} "
                        f"({imdb_id}): {e}"
                    )

            # 3. Update DB only if Telegram succeeded.
            if telegram_updated:
                try:
                    db_retry(update_movie, movie_message_id, title, alternate_title, year, imdb_id, original_language, file_languages)
                    updated_count += 1
                    logger.info(f"[~] Rebased: {title or imdb_id}")
                except Exception as e:
                    logger.error(
                        f"[!] DB update failed for {imdb_id} after Telegram caption succeeded. "
                        f"Caption is updated but DB record is stale. Error: {e}"
                    )
                    failed_count += 1
            else:
                failed_count += 1

        except Exception as e:
            logger.error(f"[!] Failed to rebase {imdb_id}: {e}")
            failed_count += 1

        time.sleep(2.0)

    bot.edit_message_text(
        text=(
            f"Rebase complete! 🔄\n"
            f"Updated: {updated_count}\n"
            f"Skipped (no TMDB data): {skipped_count}\n"
            f"Failed: {failed_count}"
        ),
        chat_id=chat_id,
        message_id=reply.message_id,
    )
    delete_after(bot, chat_id, message.message_id, 0)
    delete_after(bot, chat_id, reply.message_id, 30)


@bot.message_handler(commands=['deleteall'])
def handle_deleteall(message):
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
        delete_after(bot, chat_id, message.message_id, 0)
        delete_after(bot, chat_id, reply.message_id, 30)
    except Exception as e:
        logger.critical(
            f"[INCONSISTENCY] DB wipe failed after all Telegram deletes completed. "
            f"{len(movies)} ghost records remain. Run /deleteall again to retry. Error: {e}"
        )
        bot.edit_message_text(
            text="⚠️ Telegram messages deleted but database wipe failed. Run /deleteall again to retry.",
            chat_id=chat_id,
            message_id=reply.message_id,
        )
        delete_after(bot, chat_id, message.message_id, 0)
        delete_after(bot, chat_id, reply.message_id, 30)


@bot.message_handler(commands=['delete'])
def handle_delete(message):
    if message.chat.id != MOVIE_GROUP_ID:
        return

    if not message.reply_to_message:
        return

    target_msg_id = message.reply_to_message.message_id
    delete_after(bot, message.chat.id, message.message_id, 0)

    try:
        bot.delete_message(chat_id=message.chat.id, message_id=target_msg_id)
        logger.info(f"[-] Deleted Telegram message: {target_msg_id}")
    except Exception as e:
        logger.warning(f"[!] Failed to delete Telegram message {target_msg_id}: {e}")

    movie_record = get_movie_by_message_id(target_msg_id)
    if not movie_record:
        logger.info(f"[~] Message {target_msg_id} was not in database. Skipping DB delete.")
        return

    try:
        db_retry(delete_movie, target_msg_id)
        logger.info(f"[-] Deleted DB record: {target_msg_id}")
    except Exception as e:
        logger.critical(
            f"[INCONSISTENCY] DB delete failed after Telegram message was deleted. "
            f"GHOST RECORD: message_id={target_msg_id}. "
            f"Error: {e}"
        )
