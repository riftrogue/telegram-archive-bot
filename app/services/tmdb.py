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


def _fetch_tmdb(endpoint: str, params: dict = None):
    if params is None:
        params = {}
    params["api_key"] = TMDB_API_KEY
    
    url = f"https://api.themoviedb.org/3{endpoint}"
    try:
        response = _session.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        logger.warning(f"Connection to api.themoviedb.org failed, trying fallback api.tmdb.org...")
        fallback_url = f"https://api.tmdb.org/3{endpoint}"
        response = _session.get(fallback_url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()


def get_movie(imdb_id: str):
    """
    Look up a movie or TV show by IMDb ID using the TMDB API.
    Returns a dict with 'title', 'year', and 'language', or None on failure.
    """
    try:
        data = _fetch_tmdb(f"/find/{imdb_id}", {"external_source": "imdb_id"})
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
    params = {"query": title}
    if year:
        params["year"] = year
        
    try:
        data = _fetch_tmdb("/search/movie", params)
        results = data.get("results", [])
        if not results:
            return None
            
        # Get the first result's TMDB ID
        tmdb_id = results[0]["id"]
        
        # Fetch external IDs to get the IMDb ID
        ext_data = _fetch_tmdb(f"/movie/{tmdb_id}/external_ids")
        return ext_data.get("imdb_id")
        
    except Exception as e:
        logger.warning(f"TMDB search failed for '{title}' ({year}): {e}")
        return None