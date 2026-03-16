"""
app.py
------
Flask web server for the Movie Recommendation System.

Routes:
    GET  /            – Home page with search bar + personalized genre rows
    POST /recommend   – Accepts movie name, returns recommendations
    GET  /autocomplete– JSON endpoint for search suggestions
    POST /watch       – Add a movie to watch history
    POST /unwatch     – Remove a movie from watch history
    GET  /watched     – View all watched movies
"""

from __future__ import annotations

import json
import os
from typing import TypedDict, cast
from urllib.parse import quote_plus

from flask import Flask, jsonify, render_template, request

from env_loader import load_env_file
from recommender import (
    get_recommendations,
    get_popular_movies,
    get_personalized_sections,
    get_watched_movies,
    search_titles,
    _parse_filter_query,
)

load_env_file()

app = Flask(__name__)


class RawRecommendation(TypedDict):
    title: str
    display_title: str
    year: str | None
    language: str
    genres: str
    overview: str
    poster_url: str
    media_type: str
    score: float


class UiRecommendation(RawRecommendation):
    poster_url: str


def request_value(name: str) -> str:
    """Read a string value from Flask request data safely."""
    value = request.values.get(name, "")
    if isinstance(value, str):
        return value.strip()
    return ""


def placeholder_poster(title: str) -> str:
    """Generate a fallback poster image when no external poster is available."""
    return (
        "https://placehold.co/500x750/141414/E5E5E5"
        f"?text={quote_plus(title)}"
    )


def attach_posters(movies: list[RawRecommendation]) -> list[UiRecommendation]:
    """Ensure every recommendation has a poster URL for the web interface."""
    enriched: list[UiRecommendation] = []
    for movie in movies:
        poster_url = movie["poster_url"] or placeholder_poster(movie["display_title"])

        enriched.append(
            {
                **movie,
                "poster_url": poster_url,
            }
        )

    return enriched


# ── watch history (simple JSON file) ─────────────────────────────────────
WATCH_FILE = os.path.join(os.path.dirname(__file__), "watch_history.json")


def _load_watch_history() -> list[str]:
    if not os.path.exists(WATCH_FILE):
        return []
    with open(WATCH_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def _save_watch_history(titles: list[str]) -> None:
    with open(WATCH_FILE, "w", encoding="utf-8") as f:
        json.dump(titles, f, ensure_ascii=False, indent=2)


@app.route("/")
def home():
    """Render the home page with personalized genre rows or popular movies."""
    watched = _load_watch_history()
    sections = []
    if watched:
        raw_sections = get_personalized_sections(watched, per_section=12)
        for sec in raw_sections:
            sec["movies"] = attach_posters(cast(list[RawRecommendation], sec["movies"]))
            sections.append(sec)

    popular = attach_posters(cast(list[RawRecommendation], get_popular_movies(18)))
    return render_template(
        "index.html",
        popular_movies=popular,
        sections=sections,
        watched_count=len(watched),
    )


@app.route("/recommend", methods=["POST"])
def recommend():
    """
    Accept a movie name from the form, run the recommendation engine,
    and render the results page.
    """
    movie_name = request_value("movie_name")

    if not movie_name:
        return render_template("index.html", error="Please enter a movie name.")

    recommendations = cast(list[RawRecommendation], get_recommendations(movie_name, top_n=18))

    if not recommendations:
        return render_template(
            "index.html",
            error=f'Movie "{movie_name}" not found. Try another title.',
        )

    recommendations = attach_posters(recommendations)

    # Detect filter-type queries for better UI text
    is_filter = _parse_filter_query(movie_name) is not None

    return render_template(
        "result.html",
        movie_name=movie_name,
        recommendations=recommendations,
        is_filter=is_filter,
        result_count=len(recommendations),
    )


@app.route("/watch", methods=["POST"])
def watch():
    """Add a movie to the watch history."""
    title = request_value("title")
    if not title:
        return jsonify({"error": "No title provided"}), 400
    history = _load_watch_history()
    if title not in history:
        history.append(title)
        _save_watch_history(history)
    return jsonify({"status": "added", "title": title, "count": len(history)})


@app.route("/unwatch", methods=["POST"])
def unwatch():
    """Remove a movie from the watch history."""
    title = request_value("title")
    if not title:
        return jsonify({"error": "No title provided"}), 400
    history = _load_watch_history()
    history = [t for t in history if t != title]
    _save_watch_history(history)
    return jsonify({"status": "removed", "title": title, "count": len(history)})


@app.route("/watched")
def watched():
    """Show all watched movies."""
    history = _load_watch_history()
    movies = attach_posters(cast(list[RawRecommendation], get_watched_movies(history)))
    return render_template("watched.html", movies=movies)


@app.route("/autocomplete")
def autocomplete():
    """Return a JSON list of matching titles for the search-suggestion dropdown."""
    query = request_value("q")
    suggestions = search_titles(query)
    return jsonify(suggestions)


if __name__ == "__main__":
    # debug=True gives auto-reload during development
    app.run(debug=True, port=5000)
