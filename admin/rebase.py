import time
import logging

from bot_instance import bot
from database import get_all_movies, update_movie
from tmdb import get_movie
from utils import build_caption, db_retry

logger = logging.getLogger(__name__)


def rebase_cmd(message):
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
                # Skip this movie entirely if TMDB has no data.
                # The previous code wrote None over existing title/year/language,
                # permanently erasing metadata whenever TMDB was unavailable.
                logger.warning(
                    f"[~] TMDB returned no data for {imdb_id}. "
                    f"Skipping — existing record preserved."
                )
                skipped_count += 1
                time.sleep(2.0)
                continue

            title = new_movie_data["title"]
            year = new_movie_data["year"]
            language = new_movie_data.get("language")
            caption = build_caption(title, year, language, imdb_id)

            # 2. Update Telegram caption first (Telegram is the source of truth).
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
                    # Caption is already identical — still update the DB.
                    telegram_updated = True
                else:
                    logger.warning(
                        f"[~] Telegram caption edit failed for message {movie_message_id} "
                        f"({imdb_id}): {e}"
                    )

            # 3. Update DB only if Telegram succeeded.
            # If Telegram failed, both systems remain at their previous state — consistent.
            if telegram_updated:
                try:
                    db_retry(update_movie, movie_message_id, title, year, imdb_id, language)
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

        # Rate-limit guard: respect TMDB and Telegram API limits.
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
