import os
import time
import logging
import threading
from logging.handlers import RotatingFileHandler

from bot_instance import bot
from config import MOVIE_GROUP_ID
from database import (
    init_db,
    add_movie,
    movie_exists,
    get_movie_by_message_id,
    update_movie,
    delete_movie,
)
from tmdb import get_movie
from utils import extract_imdb, build_caption, delete_after, db_retry
from search import search
from admin.deleteall import deleteall_cmd
from admin.rebase import rebase_cmd

logger = logging.getLogger(__name__)

_START_TIME = time.monotonic()


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def _setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            RotatingFileHandler("bot.log", maxBytes=2_000_000, backupCount=3),
            logging.StreamHandler(),
        ],
    )


# ---------------------------------------------------------------------------
# Health thread — logs RSS memory and thread count every hour.
# Useful for detecting memory leaks in long-running Termux deployments.
# ---------------------------------------------------------------------------

def _health_thread():
    while True:
        time.sleep(3600)
        try:
            rss_kb = None
            with open(f"/proc/{os.getpid()}/status") as f:
                for line in f:
                    if line.startswith("VmRSS"):
                        rss_kb = int(line.split()[1])
                        break
            uptime_s = int(time.monotonic() - _START_TIME)
            logger.info(
                f"[health] rss={rss_kb}KB "
                f"threads={threading.active_count()} "
                f"uptime={uptime_s}s"
            )
        except Exception as e:
            logger.warning(f"[health] Failed to read process stats: {e}")


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

def upload(message):
    if message.chat.id != MOVIE_GROUP_ID:
        return

    media = message.document or message.video
    if not media:
        return

    imdb_id = extract_imdb(message.caption or "")
    if not imdb_id:
        return

    if movie_exists(imdb_id):
        reply_msg = bot.reply_to(message, "Movie already exists.")
        delete_after(bot, message.chat.id, reply_msg.message_id, 10)
        logger.info(f"[!] Duplicate: {imdb_id}")
        return

    movie = get_movie(imdb_id)
    if movie:
        title = movie["title"]
        year = movie["year"]
        language = movie.get("language")
    else:
        title = None
        year = None
        language = None

    caption = build_caption(title, year, language, imdb_id)

    # Telegram is source of truth: write to Telegram first.
    # Try to edit the caption in-place (works if the bot owns the message).
    # If that fails, copy the message with the correct caption and delete the original.
    try:
        bot.edit_message_caption(
            chat_id=message.chat.id,
            message_id=message.message_id,
            caption=caption,
        )
        stored_message_id = message.message_id
    except Exception:
        try:
            new_msg = bot.copy_message(
                chat_id=message.chat.id,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
                caption=caption,
            )
            bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
            stored_message_id = new_msg.message_id
        except Exception as e:
            logger.warning(f"[!] copy_message failed (rate limit?): {e}")
            # One retry after a short pause.
            time.sleep(2)
            try:
                new_msg = bot.copy_message(
                    chat_id=message.chat.id,
                    from_chat_id=message.chat.id,
                    message_id=message.message_id,
                    caption=caption,
                )
                bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
                stored_message_id = new_msg.message_id
            except Exception as e2:
                logger.warning(f"[!] copy_message failed again: {e2}")
                stored_message_id = message.message_id

    # Index in Supabase. add_movie() uses UPSERT, so retrying is safe.
    try:
        db_retry(
            add_movie,
            chat_id=message.chat.id,
            message_id=stored_message_id,
            file_unique_id=media.file_unique_id,
            file_name=getattr(media, "file_name", None),
            title=title,
            year=year,
            imdb_id=imdb_id,
            language=language,
        )
        logger.info(f"[+] Stored: {title or imdb_id}")
    except Exception as e:
        logger.critical(
            f"[INCONSISTENCY] DB insert failed after Telegram succeeded. "
            f"ORPHAN MESSAGE: chat={message.chat.id} "
            f"message_id={stored_message_id} imdb={imdb_id}. "
            f"Error: {e}"
        )


def edit_movie(message):
    if message.chat.id != MOVIE_GROUP_ID:
        return

    if not message.reply_to_message:
        return

    new_imdb_id = extract_imdb(message.text or "")
    if not new_imdb_id:
        return

    # Delete the user's edit message immediately.
    delete_after(bot, message.chat.id, message.message_id, 0)

    target_msg_id = message.reply_to_message.message_id
    movie_record = get_movie_by_message_id(target_msg_id)
    if not movie_record:
        return

    # Prevent changing to an IMDb ID that already exists for a different movie.
    if movie_record[4] != new_imdb_id and movie_exists(new_imdb_id):
        reply_msg = bot.send_message(
            chat_id=message.chat.id,
            text=f"Cannot edit: {new_imdb_id} already exists.",
        )
        delete_after(bot, message.chat.id, reply_msg.message_id, 10)
        logger.info(f"[!] Edit blocked: Duplicate {new_imdb_id}")
        return

    movie = get_movie(new_imdb_id)
    if movie:
        title = movie["title"]
        year = movie["year"]
        language = movie.get("language")
    else:
        title = None
        year = None
        language = None

    caption = build_caption(title, year, language, new_imdb_id)

    # Telegram is source of truth: update Telegram first.
    # If this fails, do not touch Supabase — both systems remain consistent.
    try:
        bot.edit_message_caption(
            chat_id=message.chat.id,
            message_id=target_msg_id,
            caption=caption,
        )
    except Exception as e:
        logger.warning(f"[!] Failed to edit caption for {target_msg_id}: {e}")
        return

    try:
        db_retry(update_movie, target_msg_id, title, year, new_imdb_id, language)
        logger.info(f"[+] Edited: {target_msg_id} → {title or new_imdb_id}")
    except Exception as e:
        logger.critical(
            f"[INCONSISTENCY] DB update failed after Telegram caption edit succeeded. "
            f"message_id={target_msg_id} new_imdb={new_imdb_id}. "
            f"Error: {e}"
        )


def delete_movie_cmd(message):
    if message.chat.id != MOVIE_GROUP_ID:
        return

    if not message.reply_to_message:
        return

    target_msg_id = message.reply_to_message.message_id

    # Delete the user's /delete command immediately.
    delete_after(bot, message.chat.id, message.message_id, 0)

    movie_record = get_movie_by_message_id(target_msg_id)
    if not movie_record:
        return

    # Telegram is source of truth: delete from Telegram first.
    # If this fails, leave the DB record intact — both systems remain consistent.
    try:
        bot.delete_message(chat_id=message.chat.id, message_id=target_msg_id)
        logger.info(f"[-] Deleted Telegram message: {target_msg_id}")
    except Exception as e:
        logger.warning(f"[!] Failed to delete Telegram message {target_msg_id}: {e}")
        return

    # Telegram delete succeeded — now clean up the DB index.
    try:
        db_retry(delete_movie, target_msg_id)
        logger.info(f"[-] Deleted DB record: {target_msg_id}")
    except Exception as e:
        logger.critical(
            f"[INCONSISTENCY] DB delete failed after Telegram message was deleted. "
            f"GHOST RECORD: message_id={target_msg_id}. "
            f"Error: {e}"
        )


# ---------------------------------------------------------------------------
# Handler registration
# ---------------------------------------------------------------------------

@bot.message_handler(content_types=['document', 'video'])
def handle_upload(message):
    upload(message)


# Also fires when a caption is edited on an existing video/document in the group.
# This covers the common workflow: forward a video → edit caption to add IMDb URL.
@bot.edited_message_handler(
    content_types=['document', 'video'],
    func=lambda m: m.chat.id == MOVIE_GROUP_ID,
)
def handle_upload_edit(message):
    upload(message)


@bot.message_handler(commands=['delete'])
def handle_delete(message):
    delete_movie_cmd(message)


@bot.message_handler(commands=['deleteall'])
def handle_deleteall(message):
    deleteall_cmd(message)


@bot.message_handler(commands=['rebase'])
def handle_rebase(message):
    rebase_cmd(message)


# Edit: a text reply that contains an IMDb URL. Must be registered before
# handle_search so that reply+IMDb messages don't fall through to search.
@bot.message_handler(
    content_types=['text'],
    func=lambda m: (
        m.reply_to_message is not None
        and extract_imdb(m.text or "") is not None
    ),
)
def handle_edit(message):
    edit_movie(message)


# Search: text messages from outside the movie group only.
# The movie group is reserved for upload, edit, and delete.
@bot.message_handler(
    content_types=['text'],
    func=lambda m: m.chat.id != MOVIE_GROUP_ID,
)
def handle_search(message):
    search(message)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    _setup_logging()
    init_db()

    threading.Thread(target=_health_thread, daemon=True).start()

    logger.info(f"Bot started. PID={os.getpid()}")

    bot.infinity_polling(timeout=20, long_polling_timeout=15)


if __name__ == "__main__":
    main()