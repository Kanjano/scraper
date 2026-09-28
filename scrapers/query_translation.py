"""Translate a search query into English, locally, before it reaches foreign shops.

Shops search their own catalogue in their own language, so "chitarra elettrica
fender" finds nothing at Sweetwater. Words are mapped to English by:

1. the gear glossary (``data/gear_glossary.json``) — curated, exact, phrases too
   ("flauto dolce" -> "recorder"). Word embeddings alone are unreliable here:
   out of context "batteria" is closer to a battery than to drums;
2. the local embedding model (see ``relevance``), for words the glossary does
   not know, onto the English gear vocabulary (``data/gear_vocabulary.txt``),
   only when the match is near-certain;
3. otherwise the word is kept: brands and models ("Fender", "Stratocaster",
   "1959") are the same in every language.

No external service is called.
"""
import json
import re
from functools import lru_cache
from pathlib import Path

from scrapers import relevance

_DATA = Path(__file__).parent / "data"
# ponytail: stricter than relevance._SAME_MEANING — a wrong translation sends a
# wrong query to 80 shops, a missed one only costs recall ("verstärker" scored
# 0.90 against "tuner").
_SURE = 0.93


@lru_cache(maxsize=1)
def _glossary() -> list[tuple[str, str]]:
    """(foreign phrase, English), longest phrase first."""
    raw = json.loads((_DATA / "gear_glossary.json").read_text(encoding="utf-8"))
    pairs = {
        relevance._norm(word): english
        for english, words in raw.items() if not english.startswith("_")
        for word in words
    }
    return sorted(pairs.items(), key=lambda p: -len(p[0]))


@lru_cache(maxsize=1)
def _vocabulary() -> list[str]:
    lines = (_DATA / "gear_vocabulary.txt").read_text(encoding="utf-8").splitlines()
    return [w.strip() for w in lines if w.strip() and not w.startswith("#")]


def _by_meaning(words: list[str]) -> dict[str, str]:
    """English vocabulary word for each word the model maps with near certainty."""
    if not words or relevance._model() is None:
        return {}
    import numpy as np

    vocab = _vocabulary()
    relevance._embed(set(words) | set(vocab))
    matrix = np.stack([relevance._VECTORS[v] for v in vocab])
    out = {}
    for w in words:
        sims = matrix @ relevance._VECTORS[w]
        best = int(sims.argmax())
        if sims[best] >= _SURE:
            out[w] = vocab[best]
    return out


def to_english(query: str) -> str | None:
    """The query in English, or None when it already is (nothing to translate)."""
    text = f" {relevance._norm(query)} "
    for foreign, english in _glossary():
        # Whole words for Latin scripts; substrings for CJK compounds (エレキギター).
        pattern = re.escape(foreign) if not foreign.isascii() else rf"(?<!\w){re.escape(foreign)}(?!\w)"
        if foreign != english:
            text = re.sub(pattern, f" {english} ", text)
    words = relevance._WORD.findall(text)
    known = set(_vocabulary()) | {e for _, e in _glossary() for e in e.split()}
    unknown = [
        w for w in words
        if w not in known and w not in relevance._STOP and not w.isdigit() and len(w) > 2
    ]
    mapped = _by_meaning(unknown)
    english = " ".join(
        mapped.get(w, w) for w in words if w not in relevance._STOP
    )
    seen: set[str] = set()  # drop repeated words, keep numbers ("4/4")
    english = " ".join(
        w for w in english.split()
        if w.isdigit() or not (w in seen or seen.add(w))
    )
    original = " ".join(w for w in relevance._words(query) if w not in relevance._STOP)
    return english if english != original else None


if __name__ == "__main__":
    assert to_english("fender stratocaster custom shop") is None
    assert to_english("chitarra elettrica fender") == "guitar electric fender"
    assert to_english("custodia per chitarra") == "case guitar"
    assert to_english("batteria elettronica roland") is not None
    assert to_english("batteria elettronica roland").startswith("drums")
    assert to_english("sax alto yamaha") is None  # "alto" is not viola here
    assert to_english("エレキギター フェンダー") .startswith("electric guitar")
    assert to_english("E-Gitarre gebraucht") == "electric guitar"  # "used" is a stop word
    assert to_english("violino 4/4") == "violin 4 4"
    assert "フェンダー" in to_english("エレキギター フェンダー")
    print("ok")
