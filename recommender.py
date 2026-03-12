"""
recommender.py
--------------
Load the trained multilingual TMDB recommendation model and expose helpers for
search suggestions and top-N content-based recommendations.
"""

import os
import re
import pickle
from difflib import get_close_matches

import numpy as np

# ── paths ────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(__file__)
MODEL_PATH = os.path.join(BASE_DIR, "model", "recommendation_model.pkl")

# ── load model once at import time ───────────────────────────────────────
with open(MODEL_PATH, "rb") as f:
    _model = pickle.load(f)

_movies = _model["movies"]
_similarity = _model["similarity"]


def _numeric_column(column_name: str, fallback: str | None = None, default: float = 0.0):
    """Return a numeric numpy array from a model column with backwards compatibility."""
    if column_name in _movies:
        return _movies[column_name].fillna(default).values.astype(float)
    if fallback and fallback in _movies:
        return _movies[fallback].fillna(default).values.astype(float)
    return np.full(len(_movies), default, dtype=float)


def _movie_text_value(index: int, column_name: str, default: str = "") -> str:
    """Read a string column from the movie dataframe safely."""
    if column_name not in _movies:
        return default
    value = _movies.iloc[index][column_name]
    if value is None:
        return default
    if isinstance(value, float) and np.isnan(value):
        return default
    return str(value)

# Pre-compute a lowercase title list for fuzzy matching
_title_list = _movies["title"].tolist()
_title_lower = [t.lower() for t in _title_list]

# Build a normalised version: "Dark Knight, The (2008)" → "the dark knight"
# This handles MovieLens' "Title, The (year)" format for better matching.
_YEAR_RE = re.compile(r"\s*\(\d{4}\)\s*$")
_ARTICLE_RE = re.compile(r",\s*(the|a|an|le|la|les|el|il|das|der|die|det|den)\s*$", re.I)

def _normalise(title: str) -> str:
    t = title.lower().strip()
    t = _YEAR_RE.sub("", t)           # remove year
    m = _ARTICLE_RE.search(t)
    if m:
        article = m.group(1)
        t = article + " " + t[:m.start()]  # move article to front
    return t.strip()

_title_normalised = [_normalise(t) for t in _title_list]

# Pre-compute a popularity score used to break similarity ties.
_vote_counts = _numeric_column("vote_count")
_vote_average = _numeric_column("vote_average", fallback="avg_rating")
_popularity_metric = _numeric_column("popularity")
_max_votes = max(_vote_counts.max(), 1)
_max_popularity = max(_popularity_metric.max(), 1)
_ranking_boost = (
    (_vote_counts / _max_votes) * 0.35
    + (_vote_average / 10.0) * 0.35
    + (_popularity_metric / _max_popularity) * 0.30
)


def get_recommendations(movie_name: str, top_n: int = 10) -> list[dict]:
    """
    Return the top-N most similar movies for a given title.

    Steps:
        1. Find the movie in the dataset (fuzzy match if needed).
        2. Look up its row index.
        3. Grab the similarity scores for that row.
        4. Sort descending and pick the top N (excluding itself).
        5. Return a list of dicts with title + genres.
    """
    # ── step 1: match the input title ────────────────────────────────────
    query_raw = movie_name.strip().lower()
    query_norm = _normalise(movie_name)
    match = None

    # Try exact (case-insensitive) match against original titles
    if query_raw in _title_lower:
        match = _title_list[_title_lower.index(query_raw)]

    # Try exact match against normalised titles  ("the dark knight" → finds it)
    if match is None and query_norm in _title_normalised:
        match = _title_list[_title_normalised.index(query_norm)]

    # Try substring match — picks shortest title containing the query
    if match is None:
        candidates = [(i, t) for i, t in enumerate(_title_normalised)
                       if query_norm in t or t in query_norm]
        if candidates:
            candidates.sort(key=lambda x: len(x[1]))
            match = _title_list[candidates[0][0]]

    # Final fallback: fuzzy match on normalised titles
    if match is None:
        close = get_close_matches(query_norm, _title_normalised, n=1, cutoff=0.5)
        if close:
            match = _title_list[_title_normalised.index(close[0])]

    if match is None:
        return []   # nothing found

    # ── step 2: get the row index ────────────────────────────────────────
    idx = _title_list.index(match)

    # ── step 3-4: combine genre similarity with popularity ─────────────
    # Primary signal is text similarity; TMDB popularity metrics break ties.
    genre_scores = _similarity[idx]
    combined = 0.82 * genre_scores + 0.18 * _ranking_boost
    combined[idx] = -1  # exclude the query movie itself

    top_indices = np.argsort(combined)[::-1][:top_n]

    # ── step 5: build result list ────────────────────────────────────────
    recommendations = []
    for i in top_indices:
        recommendations.append({
            "title": _movie_text_value(i, "title"),
            "display_title": _movie_text_value(i, "display_title", _movie_text_value(i, "title")),
            "year": _movie_text_value(i, "year") or None,
            "language": _movie_text_value(i, "language_name", "Unknown"),
            "genres": _movie_text_value(i, "genres"),
            "overview": _movie_text_value(i, "overview", "Overview not available for this movie."),
            "poster_url": _movie_text_value(i, "poster_url"),
            "score": round(float(genre_scores[i]), 4),
        })

    return recommendations


def search_titles(query: str, limit: int = 8) -> list[str]:
    """Return movie titles that contain the query string (for autocomplete)."""
    q = query.strip().lower()
    if not q:
        return []
    # Search both original and normalised titles for maximum recall
    results = [t for t, n in zip(_title_list, _title_normalised)
               if q in t.lower() or q in n]
    return results[:limit]
