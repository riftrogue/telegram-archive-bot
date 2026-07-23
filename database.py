import logging
from supabase import create_client
from config import SUPABASE_URL, SUPABASE_KEY

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Client — initialized once at module load, reused for every call.
# Creating a new client per call (the old pattern) opened a new HTTP session
# for every query. This is more efficient.
# ---------------------------------------------------------------------------

_client = create_client(SUPABASE_URL, SUPABASE_KEY)


def init_db():
    # The table is managed in the Supabase dashboard.
    # This is called at startup for compatibility; nothing to do here.
    pass


# ---------------------------------------------------------------------------
# Write operations
# ---------------------------------------------------------------------------

def add_movie(chat_id, message_id, file_unique_id, file_name, title, year, imdb_id, language=None):
    """
    Insert a new movie record. If a record with the same imdb_id already
    exists (e.g. after a crash + retry), update it instead of failing.
    Requires a UNIQUE constraint on imdb_id in the database.
    """
    data = {
        "chat_id": chat_id,
        "message_id": message_id,
        "file_unique_id": file_unique_id,
        "file_name": file_name,
        "title": title,
        "year": year,
        "imdb_id": imdb_id,
        "language": language,
    }
    _client.table("movies").upsert(data, on_conflict="imdb_id").execute()


def update_movie(message_id, title, year, new_imdb_id, language=None):
    data = {
        "title": title,
        "year": year,
        "imdb_id": new_imdb_id,
        "language": language,
    }
    _client.table("movies").update(data).eq("message_id", message_id).execute()


def delete_movie(message_id):
    _client.table("movies").delete().eq("message_id", message_id).execute()


def delete_all_movies():
    _client.table("movies").delete().neq("id", 0).execute()


# ---------------------------------------------------------------------------
# Read operations
# ---------------------------------------------------------------------------

def movie_exists(imdb_id) -> bool:
    response = _client.table("movies").select("id").eq("imdb_id", imdb_id).execute()
    return len(response.data) > 0


def search_movie(query):
    """
    Search for a movie by IMDb ID, title + year, or title only.
    Returns (chat_id, message_id, title, year, imdb_id, language) or None.
    """
    query = query.strip()

    # IMDb ID search (e.g. "tt1375666")
    if query.startswith("tt"):
        response = (
            _client.table("movies")
            .select("chat_id, message_id, title, year, imdb_id, language")
            .eq("imdb_id", query)
            .execute()
        )

    # Title + year (e.g. "Inception 2010")
    elif len(query) > 5 and query[-4:].isdigit():
        title_part = query[:-4].strip()
        year_part = int(query[-4:])
        response = (
            _client.table("movies")
            .select("chat_id, message_id, title, year, imdb_id, language")
            .ilike("title", f"%{title_part}%")
            .eq("year", year_part)
            .execute()
        )

    # Title only
    else:
        response = (
            _client.table("movies")
            .select("chat_id, message_id, title, year, imdb_id, language")
            .ilike("title", f"%{query}%")
            .execute()
        )

    if response.data:
        record = response.data[0]
        return (
            record["chat_id"],
            record["message_id"],
            record.get("title"),
            record.get("year"),
            record["imdb_id"],
            record.get("language"),
        )
    return None


def get_movie_by_message_id(message_id):
    """
    Return a movie record by its Telegram message_id, or None if not found.
    Returns (chat_id, message_id, title, year, imdb_id, language).
    """
    response = _client.table("movies").select("*").eq("message_id", message_id).execute()
    if response.data:
        record = response.data[0]
        return (
            record["chat_id"],
            record["message_id"],
            record.get("title"),
            record.get("year"),
            record["imdb_id"],
            record.get("language"),
        )
    return None


def get_all_movies():
    response = _client.table("movies").select("*").execute()
    return response.data if response.data else []
