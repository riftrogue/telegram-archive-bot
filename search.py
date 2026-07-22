import asyncio
from telegram import Update
from telegram.ext import ContextTypes
from database import search_movie
from utils import extract_imdb

async def cleanup_search(bot, chat_id, message_ids, delay: int):
    await asyncio.sleep(delay)
    for msg_id in message_ids:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception:
            pass

    try:
        inst_msg = await bot.send_message(
            chat_id=chat_id,
            text="Search cleared. Send a movie title, year, or IMDb ID to search again."
        )
        asyncio.create_task(delete_after(bot, chat_id, inst_msg.message_id, 15))
    except Exception:
        pass

async def delete_after(bot, chat_id, message_id, delay: int):
    await asyncio.sleep(delay)
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message

    if not msg.text:
        return

    asyncio.create_task(delete_after(context.bot, msg.chat_id, msg.message_id, 60))

    query = msg.text
    extracted_id = extract_imdb(query)
    if extracted_id:
        query = extracted_id

    print(f"[*] Searched: {query}")
    movie = await search_movie(query)

    if not movie:
        reply_msg = await msg.reply_text("Movie not found.")
        asyncio.create_task(delete_after(context.bot, msg.chat_id, reply_msg.message_id, 60))
        return

    chat_id, message_id, title, year, imdb_id, language = movie

    if title and year:
        caption_lines = [
            f"title: {title}",
            f"year: {year}",
        ]
        if language:
            caption_lines.append(f"language: {language}")
        caption_lines.append(f"imdb: https://www.imdb.com/title/{imdb_id}/")
        caption = "\n".join(caption_lines)
    else:
        caption = f"imdb: https://www.imdb.com/title/{imdb_id}/"

    try:
        vid_msg = await context.bot.copy_message(
            chat_id=msg.chat_id,
            from_chat_id=chat_id,
            message_id=message_id,
            caption=caption,
        )
        
        asyncio.create_task(cleanup_search(context.bot, msg.chat_id, [msg.message_id, vid_msg.message_id], 60))
    except Exception as e:
        print(f"[!] search copy failed: {e}")
