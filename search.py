import logging
import threading

from bot_instance import bot
from database import search_movie
from utils import extract_imdb, build_caption, delete_after

logger = logging.getLogger(__name__)


def _cleanup_search(chat_id, message_ids, delay):
    """
    After `delay` seconds, delete all messages in message_ids and send a
    prompt inviting the user to search again. The prompt itself is deleted
    after 15 seconds.
    """
    def _run():
        for mid in message_ids:
            try:
                bot.delete_message(chat_id=chat_id, message_id=mid)
            except Exception:
                pass
        try:
            inst_msg = bot.send_message(
                chat_id=chat_id,
                text="Search cleared. Send a movie title, year, or IMDb ID to search again.",
            )
            delete_after(bot, chat_id, inst_msg.message_id, 15)
        except Exception:
            pass

    t = threading.Timer(delay, _run)
    t.daemon = True
    t.start()


def search(message):
    if not message.text:
        return

    chat_id = message.chat.id

    # Schedule the user's search message to be deleted after 60 seconds
    # regardless of whether the search succeeds or fails.
    delete_after(bot, chat_id, message.message_id, 60)

    query = message.text
    extracted_id = extract_imdb(query)
    if extracted_id:
        query = extracted_id

    logger.info(f"[*] Searched: {query}")
    movie = search_movie(query)

    if not movie:
        reply_msg = bot.reply_to(message, "Movie not found.")
        delete_after(bot, chat_id, reply_msg.message_id, 60)
        return

    chat_id_src, message_id, title, year, imdb_id, language = movie
    caption = build_caption(title, year, language, imdb_id)

    try:
        vid_msg = bot.copy_message(
            chat_id=chat_id,
            from_chat_id=chat_id_src,
            message_id=message_id,
            caption=caption,
        )
        # Delete both the user's query and the delivered movie after 60s,
        # then prompt them to search again.
        _cleanup_search(chat_id, [message.message_id, vid_msg.message_id], 60)
    except Exception as e:
        logger.error(f"[!] search copy_message failed: {e}")
