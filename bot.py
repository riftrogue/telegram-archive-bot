import os
import re
import asyncio

from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (
    Application,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    filters,
)

from search import search
from admin.deleteall import deleteall_cmd
from admin.rebase import rebase_cmd


from database import (
    init_db,
    add_movie,
    movie_exists,
    get_movie_by_message_id,
    update_movie,
    delete_movie,
)

from tmdb import get_movie
from utils import extract_imdb

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MOVIE_GROUP_ID = int(os.getenv("MOVIE_GROUP_ID"))


async def delete_after(bot, chat_id, message_id, delay: int):
    await asyncio.sleep(delay)
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass


async def upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message

    if msg.chat_id != MOVIE_GROUP_ID:
        return

    media = msg.document or msg.video

    if not media:
        return

    imdb_id = extract_imdb(msg.caption or "")

    if not imdb_id:
        return

    if await movie_exists(imdb_id):
        reply_msg = await msg.reply_text("Movie already exists.")
        asyncio.create_task(delete_after(context.bot, msg.chat_id, reply_msg.message_id, 10))
        print(f"[!] Duplicate: {imdb_id}")
        return

    movie = await get_movie(imdb_id)

    if movie:
        title = movie["title"]
        year = movie["year"]
        language = movie.get("language")
        
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

    try:
        await context.bot.edit_message_caption(
            chat_id=msg.chat_id,
            message_id=msg.message_id,
            caption=caption,
        )
        stored_message_id = msg.message_id
    except Exception:
        # If editing fails (because the user sent it, not the bot), copy and delete
        try:
            new_msg = await context.bot.copy_message(
                chat_id=msg.chat_id,
                from_chat_id=msg.chat_id,
                message_id=msg.message_id,
                caption=caption,
            )
            await msg.delete()
            stored_message_id = new_msg.message_id
        except Exception as e:
            print(f"[!] copy_message failed (rate limit?): {e}")
            # Try one more time after a short delay
            await asyncio.sleep(2)
            try:
                new_msg = await context.bot.copy_message(
                    chat_id=msg.chat_id,
                    from_chat_id=msg.chat_id,
                    message_id=msg.message_id,
                    caption=caption,
                )
                await msg.delete()
                stored_message_id = new_msg.message_id
            except Exception as e2:
                print(f"[!] copy_message failed again: {e2}")
                stored_message_id = msg.message_id

    await add_movie(
        chat_id=msg.chat_id,
        message_id=stored_message_id,
        file_unique_id=media.file_unique_id,
        file_name=getattr(media, "file_name", None),
        title=title,
        year=year,
        imdb_id=imdb_id,
        language=language,
    )

    print(f"[+] Stored: {title or imdb_id}")


async def edit_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message

    if msg.chat_id != MOVIE_GROUP_ID:
        return

    if not msg.reply_to_message:
        return

    new_imdb_id = extract_imdb(msg.text or "")
    if not new_imdb_id:
        return

    # Delete the user's reply text
    asyncio.create_task(delete_after(context.bot, msg.chat_id, msg.message_id, 0))

    target_msg_id = msg.reply_to_message.message_id
    movie_record = await get_movie_by_message_id(target_msg_id)

    if not movie_record:
        return

    if movie_record[4] != new_imdb_id and await movie_exists(new_imdb_id):
        reply_msg = await context.bot.send_message(chat_id=msg.chat_id, text=f"Cannot edit: {new_imdb_id} already exists.")
        asyncio.create_task(delete_after(context.bot, msg.chat_id, reply_msg.message_id, 10))
        print(f"[!] Edit blocked: Duplicate {new_imdb_id}")
        return

    movie = await get_movie(new_imdb_id)
    if movie:
        title = movie["title"]
        year = movie["year"]
        language = movie.get("language")
        
        caption_lines = [
            f"title: {title}",
            f"year: {year}",
        ]
        if language:
            caption_lines.append(f"language: {language}")
        caption_lines.append(f"imdb: https://www.imdb.com/title/{new_imdb_id}/")
        caption = "\n".join(caption_lines)
    else:
        title = None
        year = None
        language = None
        caption = f"imdb: https://www.imdb.com/title/{new_imdb_id}/"

    try:
        await context.bot.edit_message_caption(
            chat_id=msg.chat_id,
            message_id=target_msg_id,
            caption=caption,
        )
    except Exception as e:
        print(f"[!] Failed to edit caption: {e}")
        return

    await update_movie(target_msg_id, title, year, new_imdb_id, language)
    print(f"[+] Edited: updated {target_msg_id} to {title or new_imdb_id}")


async def delete_movie_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message

    if msg.chat_id != MOVIE_GROUP_ID:
        return

    if not msg.reply_to_message:
        return

    target_msg_id = msg.reply_to_message.message_id
    
    # Clean up the user's /delete command
    asyncio.create_task(delete_after(context.bot, msg.chat_id, msg.message_id, 0))

    movie_record = await get_movie_by_message_id(target_msg_id)
    if not movie_record:
        return
        
    await delete_movie(target_msg_id)
    
    try:
        await context.bot.delete_message(
            chat_id=msg.chat_id,
            message_id=target_msg_id
        )
        print(f"[-] Deleted: {target_msg_id}")
    except Exception as e:
        print(f"[!] Failed to delete message {target_msg_id}: {e}")


def main():
    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & filters.TEXT,
            search,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Chat(MOVIE_GROUP_ID)
            & (filters.Document.ALL | filters.VIDEO),
            upload,
        )
    )

    app.add_handler(
        CommandHandler(
            "edit",
            edit_movie,
            filters=filters.Chat(MOVIE_GROUP_ID) & filters.REPLY
        )
    )

    app.add_handler(
        CommandHandler(
            "delete",
            delete_movie_cmd,
            filters=filters.Chat(MOVIE_GROUP_ID) & filters.REPLY
        )
    )

    app.add_handler(
        CommandHandler(
            "deleteall",
            deleteall_cmd,
            filters=filters.Chat(MOVIE_GROUP_ID)
        )
    )

    app.add_handler(
        CommandHandler(
            "rebase",
            rebase_cmd,
            filters=filters.Chat(MOVIE_GROUP_ID)
        )
    )

    print("Movie Bot Started")

    app.run_polling()


if __name__ == "__main__":
    main()