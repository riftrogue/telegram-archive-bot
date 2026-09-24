import re

# ---------------------------------------------------------------------------
# IMDb ID extraction
# ---------------------------------------------------------------------------

IMDB_RE = re.compile(r"(tt\d+)")

def extract_imdb(text: str):
    """Return the first IMDb ID found in text, or None."""
    if not text:
        return None
    match = IMDB_RE.search(text)
    return match.group(1) if match else None

# ---------------------------------------------------------------------------
# File language extraction
# ---------------------------------------------------------------------------

COMMON_LANGUAGES = [
    "Hindi", "English", "Tamil", "Telugu", "Malayalam", 
    "Kannada", "Bengali", "Marathi", "Gujarati", "Punjabi", 
    "Farsi", "Spanish", "French", "German", "Japanese", "Korean", "Chinese"
]

def extract_file_languages(filename: str):
    """
    Custom language extractor for Indian and dual-audio releases.
    """
    if not filename:
        return None
    found_langs = set()
    filename_lower = filename.lower()
    clean_filename = re.sub(r'[^a-z0-9]', ' ', filename_lower)
    
    for lang in COMMON_LANGUAGES:
        if re.search(r'\b' + lang.lower() + r'\b', clean_filename):
            found_langs.add(lang)
            
    abbreviations = {
        "hin": "Hindi", "eng": "English", "tam": "Tamil", 
        "tel": "Telugu", "mal": "Malayalam", "kan": "Kannada"
    }
    for abbr, full_lang in abbreviations.items():
        if re.search(r'\b' + abbr + r'\b', clean_filename):
            found_langs.add(full_lang)
            
    return ", ".join(sorted(list(found_langs))) if found_langs else None
