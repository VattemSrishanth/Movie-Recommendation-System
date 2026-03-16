"""
recommender.py
--------------
Load the trained KNN movie recommendation model (movies.pkl + knn_model.pkl)
and expose helpers for search suggestions, language/type filtering, and
top-N content-based recommendations.
"""

import os
import pickle
import re
import unicodedata
from difflib import get_close_matches

import numpy as np
from sklearn.neighbors import NearestNeighbors

# ── paths ────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(__file__)
MODEL_DIR = os.path.join(BASE_DIR, "model")
MOVIES_PKL = os.path.join(MODEL_DIR, "movies.pkl")
KNN_PKL = os.path.join(MODEL_DIR, "knn_model.pkl")
TFIDF_PKL = os.path.join(MODEL_DIR, "tfidf_matrix.pkl")

# ── load model once at import time ───────────────────────────────────────
with open(MOVIES_PKL, "rb") as _f:
    _movies = pickle.load(_f)

with open(KNN_PKL, "rb") as _f:
    _knn_model: NearestNeighbors = pickle.load(_f)

with open(TFIDF_PKL, "rb") as _f:
    _tfidf_matrix = pickle.load(_f)


def _safe_str(index: int, col: str, default: str = "") -> str:
    """Read a string column value safely."""
    if col not in _movies.columns:
        return default
    val = _movies.iloc[index][col]
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return default
    return str(val)


def _build_movie_dict(i: int, score: float = 1.0) -> dict:
    """Build a standard movie result dict from an index."""
    year = _safe_str(i, "year") or _safe_str(i, "release_date") or None
    if year and "-" in year:
        year = year.split("-", 1)[0]
    if year and "." in year:
        year = year.split(".", 1)[0]
    return {
        "title": _safe_str(i, "title"),
        "display_title": _safe_str(i, "display_title", _safe_str(i, "title")),
        "year": year,
        "language": _safe_str(i, "language_name", "Unknown"),
        "genres": _safe_str(i, "genres"),
        "overview": _safe_str(i, "overview", "Overview not available."),
        "poster_url": _safe_str(i, "poster_url"),
        "media_type": _safe_str(i, "media_type", "movie"),
        "score": round(float(score), 4),
    }


# ── pre-computed lookup structures ───────────────────────────────────────
_title_list = _movies["title"].tolist()
_title_lower = [t.lower() for t in _title_list]

_YEAR_RE = re.compile(r"\s*\(\d{4}\)\s*$")
_ARTICLE_RE = re.compile(
    r",\s*(the|a|an|le|la|les|el|il|das|der|die|det|den)\s*$", re.I
)


def _normalise(title: str) -> str:
    t = title.lower().strip()
    t = _YEAR_RE.sub("", t)
    # Strip Unicode diacritics (ā→a, é→e, ü→u, etc.)
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    m = _ARTICLE_RE.search(t)
    if m:
        t = m.group(1) + " " + t[: m.start()]
    return t.strip()


def _dedup_vowels(s: str) -> str:
    """Collapse consecutive duplicate vowels: 'aa'→'a', 'ee'→'e', etc."""
    out = []
    for c in s:
        if c in "aeiou" and out and out[-1] == c:
            continue
        out.append(c)
    return "".join(out)


_title_normalised = [_normalise(t) for t in _title_list]
_title_deduped = [_dedup_vowels(n) for n in _title_normalised]

# Pre-compute popularity ranking boost for tie-breaking
_vote_avg = _movies["vote_average"].fillna(0).values.astype(float) if "vote_average" in _movies else np.zeros(len(_movies))
_popularity = _movies["popularity"].fillna(0).values.astype(float) if "popularity" in _movies else np.zeros(len(_movies))
_max_pop = max(_popularity.max(), 1)
_ranking_boost = (
    (_vote_avg / 10.0) * 0.5
    + (_popularity / _max_pop) * 0.5
)

# Pre-compute language and media_type arrays for fast filtering
_languages = _movies["language_name"].fillna("").str.lower().str.strip().tolist()
_media_types = _movies["media_type"].fillna("movie").str.lower().str.strip().tolist()

# Known language names and aliases for filter detection
_LANGUAGE_NAMES = {
    "english", "hindi", "telugu", "tamil", "malayalam", "kannada",
    "bengali", "marathi", "gujarati", "punjabi", "urdu",
    "french", "german", "spanish", "italian", "portuguese",
    "japanese", "korean", "chinese", "russian", "arabic", "turkish",
    "thai", "swedish", "danish", "norwegian", "dutch", "polish",
    "czech", "romanian", "hungarian", "finnish", "greek", "hebrew",
    "indonesian", "malay", "vietnamese", "ukrainian",
}

# Media type keywords
_MEDIA_TYPE_ALIASES = {
    "movie": "movie", "movies": "movie", "film": "movie", "films": "movie",
    "series": "tv", "tv": "tv", "tv show": "tv", "tv shows": "tv",
    "show": "tv", "shows": "tv", "web series": "tv",
}


def _parse_filter_query(query: str):
    """Detect if a query is a language or media_type filter.

    Returns (filter_type, language, media_type) or None if it's a title search.
    Examples:
        "telugu movies"  → ("filter", "telugu", "movie")
        "hindi"          → ("filter", "hindi", None)
        "english series" → ("filter", "english", "tv")
        "movies"         → ("filter", None, "movie")
        "Inception"      → None
    """
    q = query.strip().lower()
    words = q.split()

    detected_lang = None
    detected_type = None

    # 1. Check multi-word media type aliases first ("tv show", "web series")
    _multi = {k: v for k, v in _MEDIA_TYPE_ALIASES.items() if " " in k}
    for alias in sorted(_multi, key=len, reverse=True):
        if alias in q:
            detected_type = _multi[alias]
            remaining = q.replace(alias, "").strip()
            for w in remaining.split():
                if w in _LANGUAGE_NAMES:
                    detected_lang = w
                    break
            break

    # 2. Check individual words for language and single-word type aliases
    if detected_type is None:
        for w in words:
            if w in _LANGUAGE_NAMES and detected_lang is None:
                detected_lang = w
            elif w in _MEDIA_TYPE_ALIASES and detected_type is None:
                detected_type = _MEDIA_TYPE_ALIASES[w]

    if detected_lang is None and detected_type is None:
        return None

    return ("filter", detected_lang, detected_type)


def _get_filtered_movies(language: str | None, media_type: str | None, top_n: int = 18) -> list[dict]:
    """Return the best movies matching a language and/or media type filter."""
    indices = []
    for i in range(len(_movies)):
        if language and _languages[i] != language:
            continue
        if media_type and _media_types[i] != media_type:
            continue
        indices.append(i)

    # Fallback: if language+type combo yields nothing, try language-only
    if not indices and language and media_type:
        indices = [i for i in range(len(_movies)) if _languages[i] == language]

    if not indices:
        return []

    # Sort by ranking boost (popularity + rating)
    boost_vals = _ranking_boost[indices]
    sorted_order = np.argsort(boost_vals)[::-1][:top_n]
    top_indices = [indices[j] for j in sorted_order]

    return [_build_movie_dict(i, _ranking_boost[i]) for i in top_indices]


def get_recommendations(movie_name: str, top_n: int = 18) -> list[dict]:
    """
    Return the top-N most similar movies for a given title, or filtered
    results when the query is a language/media_type filter.
    """
    # ── check for language / media_type filter queries ───────────────────
    filter_result = _parse_filter_query(movie_name)
    if filter_result is not None:
        _, lang, mtype = filter_result
        return _get_filtered_movies(lang, mtype, top_n)

    # ── title-based recommendation ───────────────────────────────────────
    query_raw = movie_name.strip().lower()
    query_norm = _normalise(movie_name)
    match_idx = None

    # Exact case-insensitive match on original title
    if query_raw in _title_lower:
        match_idx = _title_lower.index(query_raw)

    # Exact match on normalised titles (strips year + moves articles)
    if match_idx is None and query_norm in _title_normalised:
        match_idx = _title_normalised.index(query_norm)

    # Substring match — prefer: exact-start match, then shortest title
    if match_idx is None:
        candidates = []
        for i, (orig, norm) in enumerate(zip(_title_lower, _title_normalised)):
            if query_raw in orig or query_norm in norm:
                is_exact_norm = (norm == query_norm)
                starts = orig.startswith(query_raw) or norm.startswith(query_norm)
                candidates.append((i, orig, is_exact_norm, starts))
        if candidates:
            candidates.sort(key=lambda x: (not x[2], not x[3], len(x[1])))
            match_idx = candidates[0][0]

    # Vowel-dedup match (handles transliterations like "Baahubali" → "Bahubali")
    if match_idx is None:
        query_dedup = _dedup_vowels(query_norm)
        if query_dedup != query_norm:
            candidates = []
            for i, td in enumerate(_title_deduped):
                if query_dedup in td:
                    is_exact = (td == query_dedup)
                    starts = td.startswith(query_dedup)
                    candidates.append((i, _title_lower[i], is_exact, starts))
            if candidates:
                candidates.sort(key=lambda x: (not x[2], not x[3], len(x[1])))
                match_idx = candidates[0][0]

    # Fuzzy fallback
    if match_idx is None:
        close = get_close_matches(query_norm, _title_normalised, n=1, cutoff=0.45)
        if close:
            match_idx = _title_normalised.index(close[0])

    if match_idx is None:
        return []

    # The searched movie goes first with a perfect score
    output = [_build_movie_dict(match_idx, 1.0)]

    # Use KNN model to find nearest neighbours (fast, pre-indexed)
    distances, indices = _knn_model.kneighbors(_tfidf_matrix[match_idx])
    distances = distances.flatten()
    indices = indices.flatten()

    # Convert cosine distance → similarity score (1 - distance)
    results = []
    for dist, idx in zip(distances, indices):
        if idx == match_idx:
            continue  # skip duplicate of the query movie
        sim_score = 1.0 - dist
        combined = 0.85 * sim_score + 0.15 * _ranking_boost[idx]
        results.append((idx, sim_score, combined))

    # Sort by combined score and take top_n - 1 (first slot is the query movie)
    results.sort(key=lambda x: x[2], reverse=True)
    results = results[:top_n - 1]

    output.extend(_build_movie_dict(i, sim) for i, sim, _ in results)
    return output


def get_popular_movies(count: int = 18) -> list[dict]:
    """Return the top-N most popular movies for display on the home page."""
    top_indices = np.argsort(_ranking_boost)[::-1][:count]
    return [_build_movie_dict(i, _ranking_boost[i]) for i in top_indices]


# Pre-compute genre lists per movie for fast lookup
_genres_list = _movies["genres"].fillna("").tolist()


def _find_index_by_title(title: str) -> int | None:
    """Find the dataframe index for a movie title."""
    tl = title.strip().lower()
    norm = _normalise(title)
    if tl in _title_lower:
        return _title_lower.index(tl)
    if norm in _title_normalised:
        return _title_normalised.index(norm)
    dedup = _dedup_vowels(norm)
    for i, td in enumerate(_title_deduped):
        if dedup == td:
            return i
    return None


def _movie_has_genre(index: int, genre: str) -> bool:
    raw = _genres_list[index]
    movie_genres = [item.strip() for item in raw.replace("|", ",").split(",")]
    return genre in movie_genres


def _collect_section_movies(predicate, watched_indices: set[int], seen_movies: set[int], per_section: int) -> list[dict]:
    candidates = []
    for index in range(len(_movies)):
        if index in watched_indices or index in seen_movies:
            continue
        if predicate(index):
            candidates.append((index, _ranking_boost[index]))

    candidates.sort(key=lambda item: item[1], reverse=True)
    top = candidates[:per_section]
    for index, _score in top:
        seen_movies.add(index)
    return [_build_movie_dict(index, score) for index, score in top]


def get_personalized_sections(watched_titles: list[str], per_section: int = 12) -> list[dict]:
    """Build preference sections from watch history using genre, language, and type."""
    if not watched_titles:
        return []

    genre_counts: dict[str, int] = {}
    language_counts: dict[str, int] = {}
    media_type_counts: dict[str, int] = {}
    watched_indices: set[int] = set()

    for title in watched_titles:
        idx = _find_index_by_title(title)
        if idx is None:
            continue
        watched_indices.add(idx)

        raw = _genres_list[idx]
        for g in raw.replace("|", ",").split(","):
            g = g.strip()
            if g:
                genre_counts[g] = genre_counts.get(g, 0) + 1

        language = _languages[idx]
        if language and language != "unknown":
            language_counts[language] = language_counts.get(language, 0) + 1

        media_type = _media_types[idx]
        if media_type:
            media_type_counts[media_type] = media_type_counts.get(media_type, 0) + 1

    if not genre_counts and not language_counts and not media_type_counts:
        return []

    sections = []
    seen_movies: set[int] = set()

    top_genres = sorted(genre_counts.items(), key=lambda item: item[1], reverse=True)[:3]
    top_languages = sorted(language_counts.items(), key=lambda item: item[1], reverse=True)[:2]
    top_media_types = sorted(media_type_counts.items(), key=lambda item: item[1], reverse=True)[:1]

    for genre, _count in top_genres:
        movies = _collect_section_movies(
            lambda index, watched_genre=genre: _movie_has_genre(index, watched_genre),
            watched_indices,
            seen_movies,
            per_section,
        )
        if movies:
            sections.append(
                {
                    "title": f"More {genre}",
                    "reason": f"Because you watch {genre} titles",
                    "movies": movies,
                }
            )

    for language, _count in top_languages:
        movies = _collect_section_movies(
            lambda index, watched_language=language: _languages[index] == watched_language,
            watched_indices,
            seen_movies,
            per_section,
        )
        if movies:
            sections.append(
                {
                    "title": f"{language.title()} Picks",
                    "reason": f"Based on your {language.title()} preference",
                    "movies": movies,
                }
            )

    for media_type, _count in top_media_types:
        section_title = "Series Queue" if media_type == "tv" else "Movie Night"
        section_reason = "Built from the format you watch most"
        movies = _collect_section_movies(
            lambda index, preferred_type=media_type: _media_types[index] == preferred_type,
            watched_indices,
            seen_movies,
            per_section,
        )
        if movies:
            sections.append(
                {
                    "title": section_title,
                    "reason": section_reason,
                    "movies": movies,
                }
            )

    return sections


def get_watched_movies(watched_titles: list[str]) -> list[dict]:
    """Return full movie dicts for a list of watched titles."""
    results = []
    for title in watched_titles:
        idx = _find_index_by_title(title)
        if idx is not None:
            results.append(_build_movie_dict(idx, 1.0))
    return results


def search_titles(query: str, limit: int = 12) -> list[str]:
    """Return movie titles or filter suggestions for autocomplete.
    
    If the query looks like a language or media type, suggest filter
    phrases like "Telugu movies", "Hindi series", etc.
    """
    q = query.strip().lower()
    if not q:
        return []

    # Check if the query is starting to look like a language/type filter
    filter_suggestions = _get_filter_suggestions(q)

    # Also search for matching movie titles
    q_norm = _normalise(query)
    q_dedup = _dedup_vowels(q_norm)
    candidates = []
    for i, (title, norm) in enumerate(zip(_title_list, _title_normalised)):
        tl = title.lower()
        if q in tl or q_norm in norm or (q_dedup != q_norm and q_dedup in _title_deduped[i]):
            is_exact = (norm == q_norm)
            starts = tl.startswith(q) or norm.startswith(q_norm)
            candidates.append((title, is_exact, starts, len(title)))
    candidates.sort(key=lambda x: (not x[1], not x[2], x[3]))
    title_results = [c[0] for c in candidates[:limit]]

    # Put filter suggestions at the top
    combined = filter_suggestions + [t for t in title_results if t not in filter_suggestions]
    return combined[:limit]


def _get_filter_suggestions(q: str) -> list[str]:
    """Generate filter autocomplete suggestions for partial language/type queries."""
    suggestions = []
    q_words = q.split()

    for lang in sorted(_LANGUAGE_NAMES):
        if not lang.startswith(q) and q not in lang:
            continue
        # Check if we actually have movies in this language
        if lang not in _languages:
            continue
        cap = lang.capitalize()
        suggestions.append(f"{cap} Movies")
        if any(mt == "tv" for mt in _media_types):
            suggestions.append(f"{cap} Series")

    # Check for type-only queries like "movies", "series"
    for alias in _MEDIA_TYPE_ALIASES:
        if alias.startswith(q) and len(q) >= 2:
            if alias in ("movie", "movies", "film", "films"):
                if "Movies" not in suggestions:
                    suggestions.append("Movies")
            elif alias in ("series", "tv", "show", "shows"):
                if "Series" not in suggestions:
                    suggestions.append("Series")

    return suggestions[:4]
