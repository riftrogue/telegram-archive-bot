import re

IMDB_RE = re.compile(r"(tt\d+)")

def extract_imdb(text: str):
    if not text:
        return None

    match = IMDB_RE.search(text)
    return match.group(1) if match else None
