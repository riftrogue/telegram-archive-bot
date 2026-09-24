import logging
import threading

from app.core.bot import bot
from app.core.database import search_movie
from app.utils.extraction import extract_imdb
from app.utils.formatting import build_caption
from app.utils.core_utils import delete_after

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


@bot.message_handler(
    content_types=['text'],
    func=lambda m: m.chat.id != __import__("app.config").config.MOVIE_GROUP_ID,
)
def handle_search(message):
    search(message)

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

    chat_id_src, message_id, title, alternate_title, year, imdb_id, original_language, file_languages = movie
    caption = build_caption(title, alternate_title, year, original_language, file_languages, imdb_id)

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
