import os
import httpx
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("TMDB_API_KEY")

LANGUAGE_MAP = {
    "en": "English",
    "hi": "Hindi",
    "ml": "Malayalam",
    "ta": "Tamil",
    "te": "Telugu",
    "kn": "Kannada",
    "mr": "Marathi",
    "gu": "Gujarati",
    "pa": "Punjabi",
    "bn": "Bengali",
    "fr": "French",
    "es": "Spanish",
    "de": "German",
    "it": "Italian",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese",
    "ru": "Russian",
    "ar": "Arabic",
    "pt": "Portuguese"
}

async def get_movie(imdb_id: str):
    url = (
        f"https://api.tmdb.org/3/find/{imdb_id}"
        f"?external_source=imdb_id&api_key={API_KEY}"
    )

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url)
            response.raise_for_status()

        data = response.json()
        movies = data.get("movie_results", [])
        tv = data.get("tv_results", [])

        if movies:
            movie = movies[0]
            lang_code = movie.get("original_language")
            return {
                "title": movie["title"],
                "year": int(movie["release_date"][:4]) if movie.get("release_date") else None,
                "language": LANGUAGE_MAP.get(lang_code, lang_code.upper() if lang_code else None)
            }
        elif tv:
            show = tv[0]
            lang_code = show.get("original_language")
            return {
                "title": show.get("name") or show.get("original_name"),
                "year": int(show["first_air_date"][:4]) if show.get("first_air_date") else None,
                "language": LANGUAGE_MAP.get(lang_code, lang_code.upper() if lang_code else None)
            }
        else:
            return None

    except Exception:
        return None