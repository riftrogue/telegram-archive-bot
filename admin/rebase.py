import asyncio
from telegram import Update
from telegram.ext import ContextTypes

from database import get_all_movies, update_movie
from tmdb import get_movie

async def rebase_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message

    reply = await msg.reply_text("Fetching all movies from the database for rebase...")
    
    movies = await get_all_movies()
    if not movies:
        await reply.edit_text("Database is empty. Nothing to rebase.")
        return

    await reply.edit_text(f"Found {len(movies)} movies. Starting rebase... (sleeping 2s per movie to respect API limits)")

    updated_count = 0
    failed_count = 0

    for movie_record in movies:
        chat_id = movie_record["chat_id"]
        message_id = movie_record["message_id"]
        imdb_id = movie_record["imdb_id"]
        
        try:
            # 1. Fetch new data from TMDB
            new_movie_data = await get_movie(imdb_id)
            
            if new_movie_data:
                title = new_movie_data["title"]
                year = new_movie_data["year"]
                language = new_movie_data.get("language")
                
                caption_lines = [
                    f"title: {title}",
                    f"year: {year}",
                ]
                if language:
                    caption_lines.append(f"language: {language}")
                caption_lines.append(f"imdb: https://www.imdb.com/title/{imdb_id}/")
                caption = "\n".join(caption_lines)
            else:
                title = None
                year = None
                language = None
                caption = f"imdb: https://www.imdb.com/title/{imdb_id}/"

            # 2. Update Telegram Message Caption
            try:
                await context.bot.edit_message_caption(
                    chat_id=chat_id,
                    message_id=message_id,
                    caption=caption,
                )
            except Exception as e:
                # E.g. MessageNotModified if the caption is exactly the same, which is fine.
                print(f"[~] edit_message_caption (message {message_id}): {e}")

            # 3. Update Database Record
            await update_movie(message_id, title, year, imdb_id, language)
            updated_count += 1
            print(f"[~] Rebased: {title or imdb_id}")
            
        except Exception as e:
            print(f"[!] Failed to rebase {imdb_id}: {e}")
            failed_count += 1
            
        # VERY IMPORTANT: Rate limiting cooldown to prevent TMDB and Telegram bans
        await asyncio.sleep(2.0)
        
    await reply.edit_text(f"Rebase complete! 🔄\nUpdated: {updated_count}\nFailed: {failed_count}")
