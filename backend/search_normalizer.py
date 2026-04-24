"""
Normalizzazione query e fuzzy matching per la gestione dei typo nella ricerca.
"""

import re
import unicodedata
import logging

logger = logging.getLogger(__name__)

try:
    from rapidfuzz import fuzz, process
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    logger.warning("rapidfuzz non installato — fuzzy matching degradato a difflib")
    import difflib
    RAPIDFUZZ_AVAILABLE = False

_ACCENT_MAP = str.maketrans(
    "àáâãäåèéêëìíîïòóôõöùúûüýÿ",
    "aaaaaaeeeeiiiioooooouuuuyy"
)

_STOPWORDS = {"il", "lo", "la", "i", "gli", "le", "di", "a", "da", "in",
              "su", "con", "per", "tra", "fra", "e", "o", "un", "una"}


def normalize_query(query: str) -> str:
    """Normalizza la query: lowercase, rimozione accenti, caratteri speciali."""
    if not query:
        return ""
    result = query.lower().strip()
    result = result.translate(_ACCENT_MAP)
    # rimuovi caratteri non alfanumerici tranne spazi
    result = re.sub(r"[^\w\s]", " ", result)
    result = re.sub(r"\s+", " ", result).strip()
    return result


def get_query_tokens(query: str) -> list:
    """Restituisce i token significativi della query normalizzata."""
    normalized = normalize_query(query)
    return [t for t in normalized.split() if t not in _STOPWORDS and len(t) > 1]


def get_query_variants(query: str) -> list:
    """
    Genera varianti della query (utile per cercare forme al plurale/singolare).
    Restituisce lista di stringhe normalizzate.
    """
    normalized = normalize_query(query)
    variants = {normalized}

    # Plurale → singolare: rimuove 'e' o 's' finali
    if normalized.endswith("e") and len(normalized) > 3:
        variants.add(normalized[:-1])
    if normalized.endswith("i") and len(normalized) > 3:
        variants.add(normalized[:-1] + "a")
        variants.add(normalized[:-1] + "o")
    # Singolare → plurale
    if normalized.endswith("a") and len(normalized) > 3:
        variants.add(normalized[:-1] + "e")
    if normalized.endswith("o") and len(normalized) > 3:
        variants.add(normalized[:-1] + "i")

    return list(variants)


def fuzzy_match_score(product_name: str, query: str) -> float:
    """
    Calcola il punteggio di similarità tra nome prodotto e query (0.0 – 1.0).
    Usa rapidfuzz se disponibile, altrimenti difflib.
    """
    if not product_name or not query:
        return 0.0

    name_norm = normalize_query(product_name)
    query_norm = normalize_query(query)

    if RAPIDFUZZ_AVAILABLE:
        score = fuzz.WRatio(query_norm, name_norm) / 100.0
    else:
        score = difflib.SequenceMatcher(None, query_norm, name_norm).ratio()

    return score


def correct_typo(query: str, vocabulary: list, threshold: float = 0.75) -> str:
    """
    Data una lista di termini noti (vocabulary), restituisce il termine più simile
    alla query se il punteggio supera threshold, altrimenti restituisce la query originale.
    """
    if not vocabulary or not query:
        return query

    query_norm = normalize_query(query)

    if RAPIDFUZZ_AVAILABLE:
        match = process.extractOne(query_norm, vocabulary, scorer=fuzz.WRatio)
        if match and match[1] / 100.0 >= threshold:
            return match[0]
    else:
        matches = difflib.get_close_matches(query_norm, vocabulary, n=1, cutoff=threshold)
        if matches:
            return matches[0]

    return query


def find_similar_queries(query: str, history: list, limit: int = 5) -> list:
    """
    Dato uno storico di query (stringhe), restituisce le più simili alla query corrente.
    Usato per i suggerimenti di ricerca.
    """
    if not history or not query:
        return []

    query_norm = normalize_query(query)

    if RAPIDFUZZ_AVAILABLE:
        matches = process.extract(query_norm, history, scorer=fuzz.WRatio, limit=limit * 2)
        return [m[0] for m in matches if m[1] >= 50][:limit]
    else:
        return difflib.get_close_matches(query_norm, history, n=limit, cutoff=0.5)
