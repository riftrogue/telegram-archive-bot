import logging
import requests
from config import TMDB_API_KEY

logger = logging.getLogger(__name__)

# Session is reused across calls for HTTP connection pooling.
_session = requests.Session()

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
    "pt": "Portuguese",
}


def get_movie(imdb_id: str):
    """
    Look up a movie or TV show by IMDb ID using the TMDB API.
    Returns a dict with 'title', 'year', and 'language', or None on failure.
    """
    url = (
        f"https://api.tmdb.org/3/find/{imdb_id}"
        f"?external_source=imdb_id&api_key={TMDB_API_KEY}"
    )

    try:
        response = _session.get(url, timeout=10)
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
                "language": LANGUAGE_MAP.get(lang_code, lang_code.upper() if lang_code else None),
            }
        elif tv:
            show = tv[0]
            lang_code = show.get("original_language")
            return {
                "title": show.get("name") or show.get("original_name"),
                "year": int(show["first_air_date"][:4]) if show.get("first_air_date") else None,
                "language": LANGUAGE_MAP.get(lang_code, lang_code.upper() if lang_code else None),
            }
        else:
            return None

    except Exception as e:
        logger.warning(f"TMDB lookup failed for {imdb_id}: {e}")
        return None