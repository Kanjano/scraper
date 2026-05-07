"""Show normalize_query behavior across query variants. No new scrapes."""
from search_normalizer import normalize_query, get_query_tokens, get_query_variants, fuzzy_match_score, correct_typo

BASE = ["fender mustang", "gibson les paul", "friedman"]
VARIANTS = {
    "lower":     lambda q: q.lower(),
    "upper":     lambda q: q.upper(),
    "title":     lambda q: q.title(),
    "extra_ws":  lambda q: "  " + q.replace(" ", "  ") + "  ",
    "punct":     lambda q: f"{q}!?.",
    "accent":    lambda q: q.replace("a", "à").replace("e", "é"),
    "partial":   lambda q: q.split()[-1],  # last token
    "typo":      lambda q: q[:-1] + ("g" if q[-1] != "g" else "x"),  # 1-char swap on tail
}

print(f"{'variant':<12} {'input':<32} -> {'normalized':<32} tokens")
print("-" * 110)
for base in BASE:
    for vname, fn in VARIANTS.items():
        v = fn(base)
        n = normalize_query(v)
        t = get_query_tokens(v)
        same = "✓same" if n == normalize_query(base) else "✗diff"
        print(f"{vname:<12} {v!r:<32} -> {n!r:<32} {t} {same}")
    print()

# Typo correction demo against a small vocab
vocab = ["fender", "mustang", "gibson", "les", "paul", "friedman", "stratocaster", "jaguar"]
typos = ["fendr", "mustng", "gibsn", "freidman", "stratokaster"]
print("typo-correction (threshold 0.75):")
for t in typos:
    print(f"  {t!r:<14} -> {correct_typo(t, vocab)!r}")

# fuzzy scoring sample
print("\nfuzzy_match_score samples:")
samples = [
    ("Fender Mustang LT25", "fender mustang"),
    ("Mustang amp combo", "fender mustang"),
    ("FENDER MUSTANG GTX50", "fender mustang"),
    ("Gibson Les Paul Standard 50s", "gibson les paul"),
    ("Friedman BE-OD Overdrive", "friedman"),
    ("Random product", "fender mustang"),
]
for name, q in samples:
    s = fuzzy_match_score(name, q)
    print(f"  {q!r:<20} vs {name!r:<40} -> {s:.3f}")
