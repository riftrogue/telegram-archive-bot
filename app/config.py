import os
import sys
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MOVIE_GROUP_ID_STR = os.getenv("MOVIE_GROUP_ID")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")

# Fail immediately at startup if required configuration is missing.
# This prevents cryptic errors deep inside the bot when a variable is
# misspelled or the .env file is missing.
_missing = [
    name
    for name, value in {
        "BOT_TOKEN": BOT_TOKEN,
        "MOVIE_GROUP_ID": MOVIE_GROUP_ID_STR,
        "SUPABASE_URL": SUPABASE_URL,
        "SUPABASE_KEY": SUPABASE_KEY,
    }.items()
    if not value
]

if _missing:
    sys.exit(f"[config] Missing required environment variables: {', '.join(_missing)}")

# MOVIE_GROUP_ID is used as an int throughout the project.
MOVIE_GROUP_ID = int(MOVIE_GROUP_ID_STR)
