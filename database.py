import os
from dotenv import load_dotenv
from supabase import create_async_client, AsyncClient

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

async def get_client() -> AsyncClient:
    return await create_async_client(SUPABASE_URL, SUPABASE_KEY)


def init_db():
    # In Supabase, the table is created via the Supabase Dashboard (SQL Editor).
    pass


async def movie_exists(imdb_id):
    client = await get_client()
    response = await client.table("movies").select("id").eq("imdb_id", imdb_id).execute()
    return len(response.data) > 0


async def add_movie(chat_id, message_id, file_unique_id, file_name, title, year, imdb_id, language=None):
    client = await get_client()
    data = {
        "chat_id": chat_id,
        "message_id": message_id,
        "file_unique_id": file_unique_id,
        "file_name": file_name,
        "title": title,
        "year": year,
        "imdb_id": imdb_id,
        "language": language
    }
    await client.table("movies").insert(data).execute()


async def search_movie(query):
    client = await get_client()
    query = query.strip()

    # IMDb search
    if query.startswith("tt"):
        response = await client.table("movies").select("chat_id, message_id, title, year, imdb_id, language").eq("imdb_id", query).execute()

    # Title + Year
    elif len(query) > 5 and query[-4:].isdigit():
        title = query[:-4].strip()
        year = int(query[-4:])
        response = await client.table("movies").select("chat_id, message_id, title, year, imdb_id, language").ilike("title", f"%{title}%").eq("year", year).execute()

    # Title only
    else:
        response = await client.table("movies").select("chat_id, message_id, title, year, imdb_id, language").ilike("title", f"%{query}%").execute()

    if response.data:
        record = response.data[0]
        return (
            record["chat_id"],
            record["message_id"],
            record.get("title"),
            record.get("year"),
            record["imdb_id"],
            record.get("language")
        )
    return None


async def get_movie_by_message_id(message_id):
    client = await get_client()
    response = await client.table("movies").select("*").eq("message_id", message_id).execute()
    if response.data:
        record = response.data[0]
        return (
            record["chat_id"],
            record["message_id"],
            record.get("title"),
            record.get("year"),
            record["imdb_id"],
            record.get("language")
        )
    return None


async def update_movie(message_id, title, year, new_imdb_id, language=None):
    client = await get_client()
    data = {
        "title": title,
        "year": year,
        "imdb_id": new_imdb_id,
        "language": language
    }
    await client.table("movies").update(data).eq("message_id", message_id).execute()


async def delete_movie(message_id):
    client = await get_client()
    await client.table("movies").delete().eq("message_id", message_id).execute()


async def get_all_movies():
    client = await get_client()
    # Fetch all movies. If >1000, pagination might be needed, but for now simple select works.
    response = await client.table("movies").select("*").execute()
    return response.data if response.data else []


async def delete_all_movies():
    client = await get_client()
    # Supabase requires a filter to delete all. eq("chat_id", MOVIE_GROUP_ID) or similar, but
    # we can use not.is.null on id
    await client.table("movies").delete().neq("id", 0).execute()