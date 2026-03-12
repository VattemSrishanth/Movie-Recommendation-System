"""
app.py
------
Flask web server for the Movie Recommendation System.

Routes:
    GET  /            – Home page with search bar
    POST /recommend   – Accepts movie name, returns recommendations
    GET  /autocomplete– JSON endpoint for search suggestions
"""

from __future__ import annotations

from typing import TypedDict, cast
from urllib.parse import quote_plus

from flask import Flask, jsonify, render_template, request

from env_loader import load_env_file
from recommender import get_recommendations, search_titles

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


@app.route("/")
def home():
    """Render the home page."""
    return render_template("index.html")


@app.route("/recommend", methods=["POST"])
def recommend():
    """
    Accept a movie name from the form, run the recommendation engine,
    and render the results page.
    """
    movie_name = request_value("movie_name")

    if not movie_name:
        return render_template("index.html", error="Please enter a movie name.")

    recommendations = cast(list[RawRecommendation], get_recommendations(movie_name))

    if not recommendations:
        return render_template(
            "index.html",
            error=f'Movie "{movie_name}" not found. Try another title.',
        )

    recommendations = attach_posters(recommendations)

    return render_template(
        "result.html",
        movie_name=movie_name,
        recommendations=recommendations,
    )


@app.route("/autocomplete")
def autocomplete():
    """Return a JSON list of matching titles for the search-suggestion dropdown."""
    query = request_value("q")
    suggestions = search_titles(query)
    return jsonify(suggestions)


if __name__ == "__main__":
    # debug=True gives auto-reload during development
    app.run(debug=True, port=5000)
