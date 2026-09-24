import time
import logging
import guessit
import threading
from app.core.bot import bot
from app.config import MOVIE_GROUP_ID
from app.core.database import add_movie, movie_exists, get_movie_by_message_id, update_movie
from app.services.tmdb import get_movie, search_tmdb_by_title
from app.utils.extraction import extract_imdb, extract_file_languages
from app.utils.formatting import build_caption
from app.utils.core_utils import delete_after, db_retry

logger = logging.getLogger(__name__)

_upload_lock = threading.Lock()

def upload(message):
    with _upload_lock:
        if message.chat.id != MOVIE_GROUP_ID:
            return

        media = message.document or message.video
    if not media:
        return
        
    file_languages = None
    file_name = getattr(media, "file_name", None)
    if file_name:
        file_languages = extract_file_languages(file_name)

    def _handle_upload_error(message, error_text):
        try:
            bot.copy_message(
                chat_id=message.chat.id,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
                caption=f"{error_text}\n\n*Please reply or re-forward the file with an IMDb link to fix it.*",
                parse_mode="Markdown"
            )
            bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
        except Exception as e:
            logger.warning(f"[!] Failed to copy error video: {e}")

    imdb_id = extract_imdb(message.caption or "")
    if not imdb_id:
        if not file_name:
            _handle_upload_error(message, "❌ No IMDb ID found in caption, and this video has no filename to guess from.")
            logger.info("[!] Upload failed: No IMDb ID and no filename.")
            return
            
        logger.info(f"[*] No IMDb ID in caption. Guessing from filename: {file_name}")
        guess = guessit.guessit(file_name)
        g_title = guess.get("title")
        g_year = guess.get("year")
        
        if not g_title:
            _handle_upload_error(message, f"❌ Could not extract a movie title from the filename '{file_name}'.")
            logger.info(f"[!] guessit failed to extract title from {file_name}")
            return
            
        logger.info(f"[*] Guessed Title: '{g_title}', Year: {g_year}. Searching TMDB...")
        imdb_id = search_tmdb_by_title(g_title, g_year)
        
        if not imdb_id:
            _handle_upload_error(message, f"❌ Searched TMDB for '{g_title}' but found no matching movies.")
            logger.info(f"[!] TMDB search failed for '{g_title}' ({g_year})")
            return

    if movie_exists(imdb_id):
        reply_msg = bot.reply_to(message, "Movie already exists. Deleting this duplicate in 10s...")
        delete_after(bot, message.chat.id, reply_msg.message_id, 10)
        delete_after(bot, message.chat.id, message.message_id, 10)
        logger.info(f"[!] Duplicate: {imdb_id}")
        return

    movie = get_movie(imdb_id)
    if movie:
        title = movie["title"]
        alternate_title = movie.get("alternate_title")
        year = movie["year"]
        original_language = movie.get("original_language")
    else:
        title = None
        alternate_title = None
        year = None
        original_language = None

    caption = build_caption(title, alternate_title, year, original_language, file_languages, imdb_id)

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
        error_str = str(e).lower()
        sleep_time = 2
        import re
        match = re.search(r"retry after (\d+)", error_str)
        if match:
            sleep_time = int(match.group(1)) + 1
        
        logger.warning(f"[!] copy_message failed (rate limit). Sleeping for {sleep_time}s... Error: {e}")
        time.sleep(sleep_time)
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

    try:
        db_retry(
            add_movie,
            chat_id=message.chat.id,
            message_id=stored_message_id,
            file_unique_id=media.file_unique_id,
            file_name=getattr(media, "file_name", None),
            title=title,
            alternate_title=alternate_title,
            year=year,
            imdb_id=imdb_id,
            original_language=original_language,
            file_languages=file_languages,
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

    delete_after(bot, message.chat.id, message.message_id, 0)

    target_msg_id = message.reply_to_message.message_id
    movie_record = get_movie_by_message_id(target_msg_id)
    
    # If it's not in the DB, but they replied to a video/document, they are trying to fix a failed upload!
    if not movie_record:
        replied = message.reply_to_message
        if replied.document or replied.video:
            # Inject the IMDb ID from their reply text into the failed video's caption and process it as a fresh upload
            replied.caption = (replied.caption or "") + " " + message.text
            upload(replied)
        return

    if movie_record[5] != new_imdb_id and movie_exists(new_imdb_id):
        reply_msg = bot.send_message(
            chat_id=message.chat.id,
            text=f"Cannot edit: {new_imdb_id} already exists.",
        )
        delete_after(bot, message.chat.id, reply_msg.message_id, 10)
        logger.info(f"[!] Edit blocked: Duplicate {new_imdb_id}")
        return

    file_languages = movie_record[7] if len(movie_record) > 7 else None

    movie = get_movie(new_imdb_id)
    if movie:
        title = movie["title"]
        alternate_title = movie.get("alternate_title")
        year = movie["year"]
        original_language = movie.get("original_language")
    else:
        title = None
        alternate_title = None
        year = None
        original_language = None

    caption = build_caption(title, alternate_title, year, original_language, file_languages, new_imdb_id)

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
        db_retry(update_movie, target_msg_id, title, alternate_title, year, new_imdb_id, original_language, file_languages)
        logger.info(f"[+] Edited: {target_msg_id} → {title or new_imdb_id}")
    except Exception as e:
        logger.critical(
            f"[INCONSISTENCY] DB update failed after Telegram caption edit succeeded. "
            f"message_id={target_msg_id} new_imdb={new_imdb_id}. "
            f"Error: {e}"
        )


@bot.message_handler(content_types=['document', 'video'])
def handle_upload(message):
    upload(message)

@bot.edited_message_handler(
    content_types=['document', 'video'],
    func=lambda m: m.chat.id == MOVIE_GROUP_ID,
)
def handle_upload_edit(message):
    upload(message)

@bot.message_handler(
    content_types=['text'],
    func=lambda m: (
        m.reply_to_message is not None
        and extract_imdb(m.text or "") is not None
    ),
)
def handle_edit(message):
    edit_movie(message)
