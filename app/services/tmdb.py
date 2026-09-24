import logging
import requests
from app.config import TMDB_API_KEY

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
        f"https://api.themoviedb.org/3/find/{imdb_id}"
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
            tmdb_title = movie.get("title")
            tmdb_original = movie.get("original_title") or tmdb_title
            
            return {
                "title": tmdb_title,
                "alternate_title": tmdb_original if tmdb_original != tmdb_title else None,
                "year": int(movie["release_date"][:4]) if movie.get("release_date") else None,
                "original_language": LANGUAGE_MAP.get(lang_code, lang_code.upper() if lang_code else None),
            }
        elif tv:
            show = tv[0]
            lang_code = show.get("original_language")
            tmdb_title = show.get("name")
            tmdb_original = show.get("original_name") or tmdb_title
            
            return {
                "title": tmdb_title,
                "alternate_title": tmdb_original if tmdb_original != tmdb_title else None,
                "year": int(show["first_air_date"][:4]) if show.get("first_air_date") else None,
                "original_language": LANGUAGE_MAP.get(lang_code, lang_code.upper() if lang_code else None),
            }
        else:
            return None

    except Exception as e:
        logger.warning(f"TMDB lookup failed for {imdb_id}: {e}")
        return None


def search_tmdb_by_title(title: str, year: int = None):
    """
    Search TMDB for a movie by title (and optionally year).
    Returns the imdb_id if found, else None.
    """
    url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={title}"
    if year:
        url += f"&year={year}"
        
    try:
        response = _session.get(url, timeout=10)
        response.raise_for_status()
        
        results = response.json().get("results", [])
        if not results:
            return None
            
        # Get the first result's TMDB ID
        tmdb_id = results[0]["id"]
        
        # Fetch external IDs to get the IMDb ID
        ext_url = f"https://api.themoviedb.org/3/movie/{tmdb_id}/external_ids?api_key={TMDB_API_KEY}"
        ext_response = _session.get(ext_url, timeout=10)
        ext_response.raise_for_status()
        
        return ext_response.json().get("imdb_id")
        
    except Exception as e:
        logger.warning(f"TMDB search failed for '{title}' ({year}): {e}")
        return None