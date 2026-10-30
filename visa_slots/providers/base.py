"""Shared helpers for providers."""
import unicodedata

from curl_cffi import requests

UA_TIMEOUT = 25
ISTANBUL_WORDS = ("istanbul", "beyoglu", "altunizade", "harbiye", "gayrettepe", "kagithane")


def get(url: str, **kw):
    r = requests.get(url, impersonate="chrome", timeout=UA_TIMEOUT, **kw)
    r.raise_for_status()
    return r


def fold(s: str) -> str:
    """'İ̇Stanbul - Gayrettepe' -> 'istanbul - gayrettepe'."""
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).casefold().replace("ı", "i")


def is_istanbul(place: str) -> bool:
    p = fold(place)
    return any(w in p for w in ISTANBUL_WORDS)
