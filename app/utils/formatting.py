# ---------------------------------------------------------------------------
# Caption builder
# ---------------------------------------------------------------------------

def build_caption(title, alternate_title, year, original_language, file_languages, imdb_id: str) -> str:
    """
    Build the standard movie caption used everywhere in the bot.

    If title and year are available, includes them along with optional language.
    Falls back to just the IMDb URL if metadata is missing.
    """
    if title and year:
        lines = [
            f"title: {title}",
        ]
        if alternate_title:
            lines.append(f"alt title: {alternate_title}")
        lines.append(f"year: {year}")
        
        if original_language:
            lines.append(f"original language: {original_language}")
        if file_languages:
            lines.append(f"file languages: {file_languages}")
        lines.append(f"imdb: https://www.imdb.com/title/{imdb_id}/")
        return "\n".join(lines)

    return f"imdb: https://www.imdb.com/title/{imdb_id}/"
