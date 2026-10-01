from __future__ import annotations

import re

KENYAN_CITIES = ("Nairobi", "Mombasa", "Kisumu", "Nakuru", "Thika", "Eldoret", "Nyeri")


def anonymize_resume_text(text: str, identifiers: tuple[str, ...] = ()) -> str:
    """Remove common direct identifiers and fine-grained location from scoring text."""
    cleaned = re.sub(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", " ", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"(?:\+?\d[\d\s().-]{7,}\d)", " ", cleaned)
    cleaned = re.sub(r"\b(?:https?://|www\.)\S+", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(?:name|full name)\s*:\s*[^\n,;.]+", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(?:gender|sex|date of birth|dob|age)\s*:\s*[^\n,;]+", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b\d{1,2}\s*(?:years? old|yo)\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(?:male|female|man|woman|non-binary|nonbinary)\b", " ", cleaned, flags=re.IGNORECASE)
    for identifier in identifiers:
        if identifier.strip():
            cleaned = re.sub(rf"\b{re.escape(identifier.strip())}\b", " ", cleaned, flags=re.IGNORECASE)
    for city in KENYAN_CITIES:
        cleaned = re.sub(rf"\b{re.escape(city)}\b", " location ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(?:currently\s+)?(?:based|living|located) in location\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()
