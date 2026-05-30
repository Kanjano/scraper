"""
AdaptiveSearchOptimizer — fuzzy search + click-based learning + variant enrichment
for the music-instruments scraper.

Persists learning data to the SQLAlchemy database (ClickLog, QueryFailure,
QueryImpression, ProductVariant, QueryCorrelation) and uses it to:
  1. boost ranking of products that users actually click for a given query;
  2. suggest autocomplete entries from learned queries + product variants;
  3. expose query failures so the admin can decide which models to crawl next;
  4. enrich the index with synonyms / abbreviations / brand-model permutations.

The optimizer is *stateless at runtime* — every read goes to the DB so multiple
gunicorn workers stay coherent. An in-process cache keeps the correlation
matrix hot for the duration of a single search.
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timedelta
from typing import Iterable, Optional
from urllib.parse import urlparse

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from models import (
    db, ClickLog, ProductVariant, QueryCorrelation, QueryFailure,
    QueryImpression,
)
from search_normalizer import (
    fuzzy_match_score, normalize_query, get_query_tokens,
)

logger = logging.getLogger("search_optimizer")


# ---------------------------------------------------------------------------
# Domain knowledge — music brands and their iconic models
# ---------------------------------------------------------------------------
# Used by the variant generator. Each canonical model maps to an alias list
# (including the common abbreviated form). Lookup is case-insensitive on
# normalized tokens. Add entries as the catalog grows — this is intentionally
# hand-curated so behavior is predictable.

BRAND_ALIASES: dict[str, list[str]] = {
    "fender":       ["fender", "fmic"],
    "squier":       ["squier"],
    "gibson":       ["gibson", "gib"],
    "epiphone":     ["epiphone", "epi"],
    "ibanez":       ["ibanez", "iby"],
    "prs":          ["prs", "paul reed smith"],
    "music man":    ["music man", "musicman", "mm", "ernie ball"],
    "yamaha":       ["yamaha"],
    "martin":       ["martin", "cf martin"],
    "taylor":       ["taylor"],
    "gretsch":      ["gretsch"],
    "jackson":      ["jackson"],
    "esp":          ["esp", "ltd"],
    "schecter":     ["schecter"],
    "rickenbacker": ["rickenbacker", "rick"],
    "marshall":     ["marshall"],
    "vox":          ["vox"],
    "fender amp":   ["fender amp"],
    "mesa boogie":  ["mesa boogie", "mesa"],
    "roland":       ["roland"],
    "korg":         ["korg"],
    "moog":         ["moog"],
    "nord":         ["nord", "clavia"],
    "kawai":        ["kawai"],
    "casio":        ["casio"],
}

MODEL_ALIASES: dict[str, list[str]] = {
    # --- electric guitars ---
    "stratocaster":   ["stratocaster", "strat", "stratty"],
    "telecaster":     ["telecaster", "tele"],
    "jazzmaster":     ["jazzmaster", "jm"],
    "jaguar":         ["jaguar", "jag"],
    "mustang":        ["mustang"],
    "precision bass": ["precision bass", "p bass", "pbass", "precision"],
    "jazz bass":      ["jazz bass", "j bass", "jbass"],
    "les paul":       ["les paul", "lp", "lespaul"],
    "sg":             ["sg", "solid guitar"],
    "flying v":       ["flying v", "flyingv", "v"],
    "explorer":       ["explorer"],
    "firebird":       ["firebird"],
    "es 335":         ["es 335", "es335", "335"],
    "es 175":         ["es 175", "es175", "175"],
    "custom 24":      ["custom 24", "cu24", "custom24"],
    "silver sky":     ["silver sky", "silversky", "ss"],
    "mccarty":        ["mccarty"],
    "stingray":       ["stingray", "sr"],
    "rg":             ["rg"],
    "jem":            ["jem"],
    # --- acoustic ---
    "d 28":           ["d 28", "d-28", "d28"],
    "d 18":           ["d 18", "d-18", "d18"],
    "gs mini":        ["gs mini", "gsmini"],
    "814ce":          ["814ce"],
    # --- amps ---
    "jcm800":         ["jcm800", "jcm 800"],
    "jcm900":         ["jcm900", "jcm 900"],
    "plexi":          ["plexi"],
    "dsl":            ["dsl"],
    "ac30":           ["ac30", "ac 30"],
    "ac15":           ["ac15", "ac 15"],
    "twin reverb":    ["twin reverb", "twin"],
    "deluxe reverb":  ["deluxe reverb"],
    # --- keyboards / synths ---
    "p 125":          ["p 125", "p-125", "p125"],
    "p 45":           ["p 45", "p-45", "p45"],
    "minilogue":      ["minilogue"],
    "wavestate":      ["wavestate"],
    "juno":           ["juno"],
    "stage 3":        ["stage 3", "stage3"],
}

# Words to strip before brand/model detection (series qualifiers, finishes, years)
SERIES_NOISE = {
    "american", "americana", "professional", "pro", "ii", "iii", "deluxe",
    "standard", "vintage", "modern", "elite", "original", "ultra", "player",
    "classic", "limited", "edition", "anniversary", "60th", "65th", "70th",
    "75th", "signature", "sig", "series", "model", "reissue", "ri",
    "japan", "japanese", "mij", "usa", "mexico", "mim",
    "left", "lefty", "lh", "left handed", "righthanded",
    "black", "white", "red", "blue", "green", "sunburst", "natural",
    "candy", "apple", "olympic", "ocean", "turquoise", "pewter",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slugify(text: str) -> str:
    """Stable, URL-safe slug. Used as fallback product_key when no URL exists."""
    t = normalize_query(text)
    return re.sub(r"\s+", "-", t)[:200] if t else ""


def product_key_from_item(item: dict) -> str:
    """
    Compute a stable identifier for a product across runs.

    Preference order:
      1. Canonical URL path (drops query string / fragments) — most stable.
      2. (site + slugified name) hash — used when item has no link.
    """
    link = item.get("link") or item.get("url")
    if link:
        try:
            parsed = urlparse(link)
            host = parsed.netloc.replace("www.", "")
            path = parsed.path.rstrip("/")
            if host and path:
                return f"{host}{path}"
        except Exception:
            pass
    site = (item.get("sito") or item.get("site") or "unknown").lower()
    name = item.get("nome") or item.get("titolo") or item.get("name") or ""
    slug = _slugify(name) or hashlib.md5(name.encode()).hexdigest()[:12]
    return f"{site}:{slug}"


def _normalize_for_match(text: str) -> str:
    return normalize_query(text)


# ---------------------------------------------------------------------------
# Variant generation
# ---------------------------------------------------------------------------

def _detect_brand(tokens: list[str]) -> Optional[tuple[str, list[str]]]:
    """Return (canonical_brand, tokens_minus_brand) or None."""
    joined = " ".join(tokens)
    for canonical, aliases in BRAND_ALIASES.items():
        for alias in aliases:
            if alias in joined:
                stripped = re.sub(rf"\b{re.escape(alias)}\b", "", joined).strip()
                stripped = re.sub(r"\s+", " ", stripped)
                return canonical, stripped.split() if stripped else []
    return None


def _detect_models(text: str) -> list[str]:
    """Return canonical model names found in `text` (matched against MODEL_ALIASES)."""
    found = []
    for canonical, aliases in MODEL_ALIASES.items():
        for alias in aliases:
            if re.search(rf"\b{re.escape(alias)}\b", text):
                if canonical not in found:
                    found.append(canonical)
                break
    return found


def generate_variants(product_name: str) -> list[str]:
    """
    Generate alternative spellings / abbreviations / re-orderings for a product
    name. Returns a list of normalized strings (lowercased, accent-stripped).

    Strategy:
      * normalize the name and tokenize
      * detect brand (BRAND_ALIASES) + models (MODEL_ALIASES)
      * for each detected model, emit its full list of aliases
      * for each (brand, model) pair, emit "brand model" and "model brand"
      * emit brand alone and model alone
      * emit "no-noise" version (series qualifiers stripped)
      * always include the normalized original

    The result excludes duplicates and the empty string.
    """
    if not product_name:
        return []

    norm = normalize_query(product_name)
    tokens = norm.split()
    variants: set[str] = {norm}

    # noise-stripped form
    clean = " ".join(t for t in tokens if t not in SERIES_NOISE)
    if clean:
        variants.add(clean)

    brand_info = _detect_brand(tokens)
    brand = brand_info[0] if brand_info else None
    models = _detect_models(norm)

    # All aliases for each detected model
    for model in models:
        for alias in MODEL_ALIASES.get(model, []):
            variants.add(alias)
            if brand:
                variants.add(f"{brand} {alias}")
                variants.add(f"{alias} {brand}")

    # Brand alone is rarely useful but combo with cleaned remainder is
    if brand and clean:
        remainder = " ".join(t for t in clean.split() if t != brand)
        if remainder and remainder != brand:
            variants.add(f"{brand} {remainder}")
            variants.add(f"{remainder} {brand}")

    # Brand aliases (e.g. "music man" → "musicman")
    if brand:
        for alias in BRAND_ALIASES.get(brand, []):
            if alias != brand and clean:
                rest = re.sub(rf"\b{re.escape(brand)}\b", "", clean).strip()
                if rest:
                    variants.add(f"{alias} {rest}")

    variants.discard("")
    return sorted(variants)


# ---------------------------------------------------------------------------
# Core class
# ---------------------------------------------------------------------------

DEFAULT_CONFIG = {
    "learning_rate":        0.1,
    "min_clicks_for_boost": 1,      # apply learned boost from the 1st click
    "boost_weight":         30.0,   # max fuzzy-score points added by full correlation
    "smoothing_alpha":      1.0,    # Bayesian prior — clicks
    "smoothing_beta":       9.0,    # Bayesian prior — non-clicks
    "failure_threshold":    5,      # alert after N failures for same query
    "max_suggestions":      5,
    "max_failed_log":       1000,
}


class AdaptiveSearchOptimizer:
    def __init__(self, config: Optional[dict] = None):
        self.config = {**DEFAULT_CONFIG, **(config or {})}

    # -- search & suggestions ---------------------------------------------

    def search(self, query: str, results: list[dict],
               user_id: Optional[int] = None,
               limit: int = 50) -> list[dict]:
        """
        Re-rank `results` using fuzzy score + learned click correlations.

        The base ranking from `scraper_service.filter_and_rank_results` is
        assumed to already be price-sorted; this method overlays a learning
        boost on top of fuzzy relevance, so the *price-sort tiebreaker logic*
        still wins for items at similar correlation. Callers can decide
        whether to re-sort.
        """
        if not results:
            return []

        norm_q = normalize_query(query)
        scores = self._fetch_correlation_scores(norm_q)

        for item in results:
            base = item.get("relevance_score")
            if base is None:
                name = item.get("nome") or item.get("titolo") or item.get("name") or ""
                base = round(fuzzy_match_score(name, norm_q) * 100)
                item["relevance_score"] = base

            pk = product_key_from_item(item)
            corr = scores.get(pk, 0.0)
            boost = corr * self.config["boost_weight"]
            item["learned_boost"] = round(boost, 2)
            item["correlation_score"] = round(corr, 4)
            item["adaptive_score"] = round(base + boost, 2)
            item["product_key"] = pk

        # Stable sort by adaptive_score (desc), keep input order for ties.
        results.sort(key=lambda x: -x.get("adaptive_score", 0))
        return results[:limit]

    def get_suggestions(self, query: str, count: int = 5) -> list[str]:
        """
        Autocomplete suggestions. Combines:
          - learned queries (from ClickLog) that prefix-match
          - product variants that prefix-match
          - the normalized query itself if it's not in the set
        """
        norm = normalize_query(query)
        if not norm:
            return []

        like = f"{norm}%"
        # Learned queries (popular first)
        learned_rows = (
            db.session.query(ClickLog.normalized_query,
                             func.count(ClickLog.id).label("c"))
            .filter(ClickLog.normalized_query.like(like))
            .group_by(ClickLog.normalized_query)
            .order_by(func.count(ClickLog.id).desc())
            .limit(count * 2)
            .all()
        )
        learned = [r[0] for r in learned_rows]

        # Variant matches
        variant_rows = (
            db.session.query(ProductVariant.variant)
            .filter(ProductVariant.variant.like(like))
            .distinct()
            .limit(count * 2)
            .all()
        )
        variants = [r[0] for r in variant_rows]

        seen: set[str] = set()
        out: list[str] = []
        for s in learned + variants:
            if s and s not in seen:
                seen.add(s)
                out.append(s)
                if len(out) >= count:
                    break
        return out

    # -- learning hooks ---------------------------------------------------

    def record_click(self, user_id: Optional[int], query: str,
                     product: dict, rank: Optional[int] = None) -> None:
        """Persist a click and update the query→product correlation score."""
        norm = normalize_query(query)
        pk = product_key_from_item(product)
        name = product.get("nome") or product.get("titolo") or product.get("name") or ""
        site = product.get("sito") or product.get("site")

        db.session.add(ClickLog(
            user_id=user_id, query=query, normalized_query=norm,
            product_key=pk, product_name=name, site=site, click_rank=rank,
        ))
        self._bump_correlation(norm, pk, name, clicks_delta=1)
        db.session.commit()

    def record_no_result(self, query: str) -> dict:
        """Persist a zero-results query. Returns alert info if threshold tripped."""
        norm = normalize_query(query)
        db.session.add(QueryFailure(
            query=query, normalized_query=norm, results_count=0,
        ))
        db.session.commit()
        count = (
            db.session.query(func.count(QueryFailure.id))
            .filter(QueryFailure.normalized_query == norm)
            .scalar()
        ) or 0
        alert = count >= self.config["failure_threshold"]
        if alert:
            logger.warning(
                "Query failure threshold tripped for %r (failures=%d) — "
                "consider running a targeted crawl for this term.",
                norm, count,
            )
        return {"normalized_query": norm, "failures": count, "alert": alert}

    def record_impression(self, user_id: Optional[int], query: str,
                          result_count: int,
                          shown_product_keys: Optional[Iterable[str]] = None) -> None:
        """Record that a query was run with N results.

        If `shown_product_keys` is provided, bumps impression_count on the
        per-product correlation rows so CTR-style scoring stays calibrated.
        """
        norm = normalize_query(query)
        db.session.add(QueryImpression(
            normalized_query=norm, results_count=result_count,
        ))
        if shown_product_keys:
            for pk in shown_product_keys:
                self._bump_correlation(norm, pk, product_name=None,
                                       impressions_delta=1)
        db.session.commit()

    # -- enrichment / crawl ------------------------------------------------

    def enrich_index(self, products: Iterable[dict]) -> dict:
        """
        Iterate over products and generate variants for any new ones.
        Returns counters: {scanned, new_products, new_variants}.

        Typically called on-demand via /api/optimizer/enrich after a fresh
        scrape pass. Safe to re-run — duplicates are skipped by unique key.
        """
        scanned = 0
        new_products = 0
        new_variants = 0

        seen_in_batch: set[str] = set()

        for item in products:
            scanned += 1
            name = item.get("nome") or item.get("titolo") or item.get("name")
            if not name:
                continue
            pk = product_key_from_item(item)
            if pk in seen_in_batch:
                continue
            seen_in_batch.add(pk)

            existing = (
                db.session.query(ProductVariant.variant)
                .filter(ProductVariant.product_key == pk)
                .all()
            )
            existing_set = {r[0] for r in existing}
            if not existing_set:
                new_products += 1

            for variant in generate_variants(name):
                if variant in existing_set:
                    continue
                db.session.add(ProductVariant(
                    product_key=pk, main_name=name,
                    variant=variant, source="rules",
                ))
                try:
                    db.session.flush()
                    new_variants += 1
                    existing_set.add(variant)
                except IntegrityError:
                    db.session.rollback()

        db.session.commit()
        logger.info(
            "enrich_index: scanned=%d new_products=%d new_variants=%d",
            scanned, new_products, new_variants,
        )
        return {
            "scanned": scanned,
            "new_products": new_products,
            "new_variants": new_variants,
        }

    def update_synonyms(self, product_key: str, main_name: str,
                        new_variants: Iterable[str],
                        source: str = "manual") -> int:
        """Add manually-provided variants for a product. Returns count added."""
        added = 0
        for v in new_variants:
            v_norm = normalize_query(v)
            if not v_norm:
                continue
            row = ProductVariant(
                product_key=product_key, main_name=main_name,
                variant=v_norm, source=source,
            )
            db.session.add(row)
            try:
                db.session.flush()
                added += 1
            except IntegrityError:
                db.session.rollback()
        db.session.commit()
        return added

    # -- analytics --------------------------------------------------------

    def get_failed_queries(self, limit: int = 20,
                           days: Optional[int] = None) -> list[dict]:
        """
        Top failed queries with failure count. Optionally restrict to the
        last `days` days.
        """
        q = db.session.query(
            QueryFailure.normalized_query,
            func.count(QueryFailure.id).label("failures"),
            func.max(QueryFailure.timestamp).label("last_seen"),
        )
        if days:
            cutoff = datetime.utcnow() - timedelta(days=days)
            q = q.filter(QueryFailure.timestamp >= cutoff)
        rows = (
            q.group_by(QueryFailure.normalized_query)
             .order_by(func.count(QueryFailure.id).desc())
             .limit(limit)
             .all()
        )
        threshold = self.config["failure_threshold"]
        return [
            {
                "query": r[0],
                "failures": r[1],
                "last_seen": r[2].isoformat() if r[2] else None,
                "alert": r[1] >= threshold,
            }
            for r in rows
        ]

    def get_most_searched(self, days: int = 7, limit: int = 20) -> list[dict]:
        """Most-frequent queries over `days`. Pulls from QueryImpression."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        rows = (
            db.session.query(
                QueryImpression.normalized_query,
                func.count(QueryImpression.id).label("c"),
            )
            .filter(QueryImpression.timestamp >= cutoff)
            .group_by(QueryImpression.normalized_query)
            .order_by(func.count(QueryImpression.id).desc())
            .limit(limit)
            .all()
        )
        return [{"query": r[0], "count": r[1]} for r in rows]

    def get_product_variants(self, product_key: str) -> list[str]:
        rows = (
            db.session.query(ProductVariant.variant)
            .filter(ProductVariant.product_key == product_key)
            .order_by(ProductVariant.variant)
            .all()
        )
        return [r[0] for r in rows]

    def get_correlation_score(self, query: str, product_key: str) -> float:
        norm = normalize_query(query)
        row = (
            db.session.query(QueryCorrelation.score)
            .filter(
                QueryCorrelation.normalized_query == norm,
                QueryCorrelation.product_key == product_key,
            )
            .first()
        )
        return float(row[0]) if row else 0.0

    def get_training_stats(self) -> dict:
        """Counts for diagnostics dashboard."""
        clicks = db.session.query(func.count(ClickLog.id)).scalar() or 0
        failures = db.session.query(func.count(QueryFailure.id)).scalar() or 0
        impressions = db.session.query(func.count(QueryImpression.id)).scalar() or 0
        variants = db.session.query(func.count(ProductVariant.id)).scalar() or 0
        correlations = db.session.query(func.count(QueryCorrelation.id)).scalar() or 0
        unique_queries = (
            db.session.query(func.count(func.distinct(ClickLog.normalized_query)))
            .scalar()
        ) or 0
        return {
            "clicks": clicks,
            "failures": failures,
            "impressions": impressions,
            "variants": variants,
            "correlations": correlations,
            "unique_clicked_queries": unique_queries,
        }

    # -- internal ---------------------------------------------------------

    def _fetch_correlation_scores(self, normalized_query: str) -> dict[str, float]:
        """Return {product_key: score} for the given normalized query."""
        rows = (
            db.session.query(QueryCorrelation.product_key, QueryCorrelation.score)
            .filter(QueryCorrelation.normalized_query == normalized_query)
            .all()
        )
        return {r[0]: float(r[1] or 0.0) for r in rows}

    def _bump_correlation(self, normalized_query: str, product_key: str,
                          product_name: Optional[str],
                          clicks_delta: int = 0,
                          impressions_delta: int = 0) -> None:
        """
        Bayesian-smoothed CTR update. Score = (clicks + alpha) /
        (impressions + alpha + beta), clamped to [0, 1].

        Reads-then-writes inside a single session; the caller commits.
        """
        row = (
            db.session.query(QueryCorrelation)
            .filter(
                QueryCorrelation.normalized_query == normalized_query,
                QueryCorrelation.product_key == product_key,
            )
            .first()
        )
        if row is None:
            row = QueryCorrelation(
                normalized_query=normalized_query,
                product_key=product_key,
                product_name=product_name,
                click_count=0,
                impression_count=0,
                score=0.0,
            )
            db.session.add(row)

        row.click_count = (row.click_count or 0) + clicks_delta
        row.impression_count = (row.impression_count or 0) + impressions_delta
        # impressions never less than clicks (a click implies an impression)
        if row.impression_count < row.click_count:
            row.impression_count = row.click_count
        if product_name and not row.product_name:
            row.product_name = product_name

        alpha = self.config["smoothing_alpha"]
        beta = self.config["smoothing_beta"]
        clicks = row.click_count
        imps = row.impression_count
        score = (clicks + alpha) / (imps + alpha + beta)
        row.score = max(0.0, min(1.0, score))
