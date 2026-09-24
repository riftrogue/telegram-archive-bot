import re

COMMON_LANGUAGES = [
    "Hindi", "English", "Tamil", "Telugu", "Malayalam", 
    "Kannada", "Bengali", "Marathi", "Gujarati", "Punjabi", 
    "Farsi", "Spanish", "French", "German", "Japanese", "Korean", "Chinese"
]

def extract_languages_from_filename(filename: str):
    if not filename: return None
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

files = [
    "The_Godfather_Part_II_1974_720p_BDRip_Tamil_+_Hindi_+_English_x264.mkv",
    "Green.Book.2018.720p.Farsi.Dubbed.mkv",
    "Vaazha (2024) Dual Audio [Hindi - Malayalam] Movie HD ES.mkv",
    "RK-RKAY.2021.Hin.WEB.Dogemovies.xyz.DL.2.0.1080p.ESub.mkv"
]
for f in files:
    print(f, "->", extract_languages_from_filename(f))
