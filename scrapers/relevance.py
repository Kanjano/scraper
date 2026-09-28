"""Keep only offers that match what the user typed.

Shops' own search engines are loose (any word, fuzzy, "popular items" when
nothing matches) and grid pages can carry unrelated products, so every offer is
checked again here, whichever scraper produced it:

* every word of the query must appear in the offer's name or brand. A word
  matches a name word it starts ("strat" -> "stratocaster") or that starts it,
  when that is at least 4 letters ("stratocaster" -> "Strat"), or — through a
  local multilingual embedding model, no external service — a name word with
  the same meaning in another language ("chitarra" -> "guitar", "Gitarre",
  "ギター"). Function words ("per", "for", "mit") are ignored;
* parts and accessories (pickups, screws, cables…) are kept only as secondary
  results unless the query asks for them, so "fender stratocaster" ranks
  guitars, and a pickup set does not become the "lowest price". A part word
  alone is not enough — guitars mention "maple neck", "w/case", "Josefina
  pickups" — the offer must also cost far less than the typical match.
"""
import re
import unicodedata
from functools import lru_cache
from statistics import median

from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)

_WORD = re.compile(r"\w+")

# ponytail: keyword list, EN/IT/DE/FR/ES; extend when a shop's parts leak through.
_ACCESSORY = {
    "pickup", "pickups", "pu", "tonabnehmer", "pickguard", "battipenna", "screw",
    "screws", "viti", "vite", "knob", "knobs", "manopola", "manopole", "switch",
    "selector", "bridge", "ponte", "saddle", "saddles", "tremolo", "tuner",
    "tuners", "meccaniche", "mechaniken", "nut", "string", "strings", "corde",
    "saiten", "cordes", "cuerdas", "cable", "cavo", "kabel", "strap", "tracolla",
    "gurt", "case", "custodia", "koffer", "etui", "estuche", "gigbag", "bag",
    "borsa", "stand", "supporto", "pedal", "pedale", "pick", "picks", "plettro",
    "plettri", "capo", "book", "libro", "buch", "dvd", "poster", "shirt", "tshirt",
    "hoodie", "mug", "cap", "sticker", "decal", "gift", "neck", "manico", "hals",
    "body", "corpo", "korpus", "parts", "part", "ricambi", "replacement", "cover",
    "plate", "backplate", "spring", "springs", "insert", "inserts", "wiring",
    "harness", "pot", "pots", "potentiometer", "jack", "polish", "cleaner",
    "slagplaat", "snaren", "hoes", "tee", "puzzle", "trucker", "snijplank",
    "topkam", "muta", "mute", "sordina", "rosin", "colofonia", "chinrest",
    "mentoniera", "shoulder", "spalliera", "bow", "archetto",
    # printed/digital content, not the instrument
    "scales", "arpeggios", "method", "metodo", "songbook", "sheet", "spartito",
    "spartiti", "partitura", "noten", "abrsm", "grade", "lesson", "lessons",
    "pece", "studies", "etudes", "exercises", "esercizi", "basics",
    "tuning", "machine", "machines", "upgrade", "hanger", "mount", "holder", "wall",
    "humidity", "dampit", "miniature",
    # sheet music: catalogue numbers and forms
    "op", "kv", "bwv", "concerto", "konzert", "violinkonzert", "sonata", "sonate",
    "school", "schule", "scuola", "volume", "vol", "duets", "etude",
    "delivery", "download", "license", "licence", "expansion", "samples", "plugin",
}


def _norm(text: str) -> str:
    """Lowercase without Latin accents ("clásica" -> "clasica"). Marks on other
    scripts are part of the letter (フェンダー must not become フェンター)."""
    out: list[str] = []
    for c in unicodedata.normalize("NFKD", text or ""):
        if unicodedata.combining(c) and out and ord(out[-1]) < 0x250:
            continue
        out.append(c)
    return unicodedata.normalize("NFC", "".join(out)).lower()


def _words(text: str) -> list[str]:
    return _WORD.findall(_norm(text))


# Function words of the site's languages: never required in a product name.
_STOP = {
    "a", "an", "the", "for", "with", "and", "or", "of", "in", "to", "new", "used",
    "il", "lo", "la", "i", "gli", "le", "un", "una", "uno", "di", "da", "per", "con",
    "e", "o", "del", "della", "dei", "delle", "nuovo", "nuova", "usato", "usata",
    "el", "los", "las", "para", "y", "de", "con", "nuevo", "usado",
    "le", "les", "des", "du", "pour", "avec", "et", "neuf", "occasion",
    "der", "die", "das", "ein", "eine", "fur", "mit", "und", "oder", "neu", "gebraucht",
    "o", "os", "as", "um", "uma", "com", "novo",
}


def query_terms(query: str) -> list[str]:
    return list(dict.fromkeys(
        w for w in _words(query) if (len(w) > 1 or w.isdigit()) and w not in _STOP
    ))


def _term_matches(term: str, words: list[str], haystack: str) -> bool:
    if not term.isascii():  # CJK etc.: no spaces between words, match as substring
        return term in haystack
    return any(
        w.startswith(term) or (len(w) >= 4 and term.startswith(w)) for w in words
    )


def _haystack(offer: dict) -> str:
    return _norm(f"{offer.get('brand') or ''} {offer.get('name') or ''}")


def _missing(offer: dict, terms: list[str]) -> tuple[list[str], list[str]]:
    """The offer's name/brand words and the query terms they do not cover.

    Shop-supplied ``keywords`` (Thomann's card bullets: "Modello Murphy Lab"
    for "Les Paul 57 Goldtop ULA") may cover the rest, literally, but only when
    the name itself matches a term: brand + "Strat" in a pickguard's bullets
    must not pass for "fender stratocaster".
    """
    haystack = _haystack(offer)
    words = _WORD.findall(haystack)
    missing = [t for t in terms if not _term_matches(t, words, haystack)]
    extra = _norm(offer.get("keywords") or "")
    if missing and extra:
        name = _words(offer.get("name") or "")
        if any(_term_matches(t, name, " ".join(name)) for t in terms):
            more = _WORD.findall(extra)
            missing = [t for t in missing if not _term_matches(t, more, extra)]
    return words, missing


def matches(offer: dict, terms: list[str]) -> bool:
    return not _missing(offer, terms)[1]


# ponytail: measured on it/en/de/fr/ja word pairs with MiniLM — translations
# score >= 0.90, distinct instruments/models <= 0.75. Lower it for more recall.
_SAME_MEANING = 0.85


@lru_cache(maxsize=1)
def _model():
    """The local embedding model, or None (lexical matching only)."""
    if not settings.semantic_model:
        return None
    try:
        from fastembed import TextEmbedding
    except ImportError as exc:
        logger.warning("semantic matching off: %s", exc)
        return None
    args = (settings.semantic_model,)
    try:  # already downloaded: load it without touching the network
        return TextEmbedding(*args, cache_dir=settings.models_dir, local_files_only=True)
    except Exception:  # noqa: BLE001 — first run: download once
        pass
    try:
        return TextEmbedding(*args, cache_dir=settings.models_dir)
    except Exception as exc:  # noqa: BLE001 — no network / bad model name
        logger.warning("semantic matching off, model unavailable: %s", exc)
        return None


_VECTORS: dict[str, "object"] = {}  # word -> unit vector, shared across searches


def _embed(words: set[str]) -> None:
    import numpy as np

    todo = [w for w in words if w not in _VECTORS]
    if todo:
        for w, v in zip(todo, _model().embed(todo)):
            _VECTORS[w] = v / (np.linalg.norm(v) or 1.0)
    if len(_VECTORS) > 200_000:  # ponytail: crude bound on the cache
        _VECTORS.clear()


def filter_relevant(offers: list[dict], query: str) -> list[dict]:
    """Offers whose name/brand covers every query term, literally or by meaning."""
    terms = query_terms(query)
    if not terms:
        return list(offers)
    kept, pending = [], []
    for o in offers:
        words, missing = _missing(o, terms)
        if not missing:
            kept.append(o)
        else:
            pending.append((o, words, missing))
    if not pending or _model() is None:
        return kept

    needed = {t for _, _, miss in pending for t in miss}
    _embed(needed | {w for _, words, _ in pending for w in words})
    import numpy as np

    for o, words, missing in pending:
        if not words:
            continue
        name_vecs = np.stack([_VECTORS[w] for w in words])
        if all(float((name_vecs @ _VECTORS[t]).max()) >= _SAME_MEANING for t in missing):
            kept.append(o)
    return kept


# "Rosin for violin", "pece per violino": what follows these is what the product
# is *for*, not what it is.
_FOR = {"for", "per", "fur", "pour", "para", "voor", "fuer", "icin"}
# What follows these is a feature of the product: "Strat w/ case", "with neck".
_WITH = {"with", "w", "con", "completo", "completa", "mit", "avec", "incl",
         "inkl", "including", "includes", "plus", "and", "und", "et"}
_STRINGS = {"string", "strings", "corde", "saiten", "cuerdas", "cordes", "snaren"}


_SEGMENTS = re.compile(r",| - | \| |\(|\)")


def _head_words(name: str, terms: list[str]) -> list[str]:
    """The words that say what the product is: the segment of the name holding
    the query ("Fender - Standard Stratocaster, Laurel Fingerboard, White
    Pickguard" -> "standard stratocaster"), cut before a "with …" feature list."""
    segments = [_words(s) for s in _SEGMENTS.split(name)]
    head = next(
        (s for s in segments if any(_term_matches(t, s, " ".join(s)) for t in terms)),
        _words(name),
    )
    out = []
    for w in head:
        if w in _WITH:
            break
        out.append(w)
    return out


def _mentions_part(offer: dict, terms: list[str]) -> bool:
    words = _head_words(offer.get("name") or "", terms)
    for i, w in enumerate(words):
        if w in _ACCESSORY and w not in terms:
            if w in _STRINGS and i and words[i - 1].isdigit():
                continue  # "6 String Electric Guitar" describes the guitar
            return True
    return False


def _made_for(offer: dict, terms: list[str]) -> bool:
    """The query's words only appear after "for"/"per"/…: an accessory for it."""
    words = _words(offer.get("name") or "")
    if not any(w in _FOR for w in words):
        return False
    first_for = next(i for i, w in enumerate(words) if w in _FOR)
    before = words[:first_for]
    hits = [t for t in terms if t.isascii() and not t.isdigit()]
    return bool(hits) and not any(_term_matches(t, before, " ".join(before)) for t in hits)


def score(offer: dict, terms: list[str]) -> float:
    """How closely an offer that already matches the query fits it, 0..1.

    Exact words beat prefixes and translations, a concise name beats one where
    the query is lost among other words, query order and an early match help.
    Accessories are halved: they match the words, not the intent.
    """
    words = _WORD.findall(_haystack(offer))
    if not terms or not words:
        return 0.0
    exact = sum(t in words for t in terms) / len(terms)
    brevity = min(1.0, len(terms) / len(words))
    positions = [words.index(t) for t in terms if t in words]
    in_order = sum(b > a for a, b in zip(positions, positions[1:])) / max(1, len(terms) - 1)
    early = 1 / (1 + (min(positions) if positions else len(words)) / 4)
    value = 0.45 * exact + 0.25 * brevity + 0.15 * in_order + 0.15 * early
    return round(value * (0.5 if offer.get("is_accessory") else 1.0), 4)


# ponytail: fixed ratios of the median price of offers without part words.
# A part word under 30% of it is an accessory; anything under 5% is one even
# without a known part word (a €0.56 exercise book among violins).
_CHEAP = 0.3
_TRIVIAL = 0.05


def flag_accessories(offers: list[dict], terms: list[str], key: str = "price_eur_equivalent"):
    """Set ``is_accessory`` on each offer: made "for" the query's item, or a part
    word the query did not ask for at a price well below the typical offer."""
    parts = {id(o): _mentions_part(o, terms) for o in offers}
    clean = [o[key] for o in offers if o.get(key) and not parts[id(o)]]
    prices = clean or [o[key] for o in offers if o.get(key)]
    mid = median(prices) if prices else 0
    for o in offers:
        price = o.get(key) or 0
        o["is_accessory"] = (
            _made_for(o, terms)
            or price < mid * _TRIVIAL
            or (parts[id(o)] and price < mid * _CHEAP)
        )
    return offers


if __name__ == "__main__":
    t = query_terms("Fender Stratocaster Custom Shop")
    assert t == ["fender", "stratocaster", "custom", "shop"]
    guitar = {"name": "Custom Shop '56 Strat Relic", "brand": "Fender", "p": 4000}
    neck = {"name": "Fender Custom Shop '57 Stratocaster with Matching Neck", "p": 4400}
    pickups = {"name": "Custom Shop Fat '50s Stratocaster Pickup Set", "brand": "Fender", "p": 280}
    assert matches(guitar, t) and matches(pickups, t)
    flag_accessories([guitar, neck, pickups], t, key="p")
    assert not guitar["is_accessory"] and not neck["is_accessory"] and pickups["is_accessory"]
    assert not matches({"name": "Slate Digital Custom Series Bundle"}, t)
    assert not matches({"name": "Fender Telecaster Custom Shop"}, t)
    ml = {"name": "Les Paul 57 Goldtop ULA", "brand": "Gibson"}
    assert not matches(ml, query_terms("gibson les paul murphy lab"))
    assert matches({**ml, "keywords": "Modello Murphy Lab Custom Shop"},
                   query_terms("gibson les paul murphy lab"))
    assert not matches({"name": "Pre-Wired ST Pickg.", "brand": "Fender",
                        "keywords": "Battipenna Vintage Noiseless Strat"},
                       query_terms("fender stratocaster"))
    assert matches({"name": "Fender Stratocaster"}, query_terms("fender strat"))
    assert matches({"name": "フェンダー ストラトキャスター"}, query_terms("ストラト"))
    flag_accessories([guitar, pickups], query_terms("fender stratocaster pickup"), key="p")
    assert not pickups["is_accessory"]
    assert query_terms("custodia per chitarra") == ["custodia", "chitarra"]
    offers = [{"name": "Fender Player Stratocaster Electric Guitar"},
              {"name": "Fender Precision Bass"}, {"name": "Yamaha P-45 Digital Piano"}]
    got = [o["name"] for o in filter_relevant(offers, "chitarra elettrica fender")]
    if _model() is not None:
        assert got == ["Fender Player Stratocaster Electric Guitar"], got
    v = query_terms("violin")
    for name, acc in [
        ("GEWA Pece per violino", True), ("Hal Leonard - Christmas Carols for Violin", True),
        ("Hercules Violin Wall Hanger", False),  # no rule knows "hanger": price decides
        ("SMIGER 4/4 Size Violin Ready to Play with Carrying Case", False),
        ("VIOLINO SOUNDSATION ORC-14 completo di astucci", False),
    ]:
        assert _made_for({"name": name}, query_terms("violino violin")) == acc, name
    s = query_terms("fender stratocaster")
    assert not _mentions_part({"name": "Fender JP24 Stratocaster 6 String Electric Guitar"}, s)
    assert not _mentions_part({"name": "Fender Eric Clapton Stratocaster w/ Case"}, s)
    assert _mentions_part({"name": "Fender Classic Series Strat/Tele Case Tweed"}, s)
    assert not _mentions_part({"name": "Fender - Standard Stratocaster, Laurel "
                                        "Fingerboard, White Pickguard"}, s)
    assert _mentions_part({"name": "D'Addario, Acoustic Guitar Strings, 85/15 Bronze"},
                          query_terms("guitar"))
    assert _mentions_part({"name": "Mozart - Violinkonzert [NR. 2] D-dur KV 211"}, v)
    assert _made_for({"name": "Fender slagplaat voor Stratocaster 3-laags zwart"}, s) is False
    q = query_terms("fender stratocaster")
    assert score({"name": "Fender Stratocaster"}, q) > score(
        {"name": "Squier by Fender Classic Vibe 60s Stratocaster Laurel"}, q)
    assert score({"name": "Fender Stratocaster"}, q) > score(
        {"name": "Fender Stratocaster", "is_accessory": True}, q)
    print("ok")
