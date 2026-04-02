"""
backend/api_bridge.py
---------------------
Bridge script used by the JavaScript backend to call Python recommender logic.
Prints JSON only to stdout for easy machine parsing.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

# Allow importing root-level recommender.py while keeping bridge in backend/
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from recommender import (  # noqa: E402
    _parse_filter_query,
    get_personalized_sections,
    get_popular_movies,
    get_recommendations,
    get_watched_movies,
    search_titles,
)


def placeholder_poster(title: str) -> str:
    return (
        "https://placehold.co/500x750/141414/E5E5E5"
        f"?text={quote_plus(title)}"
    )


def attach_posters(movies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for movie in movies:
        copy_movie = dict(movie)
        display_title = str(copy_movie.get("display_title") or copy_movie.get("title") or "Movie")
        copy_movie["poster_url"] = copy_movie.get("poster_url") or placeholder_poster(display_title)
        enriched.append(copy_movie)
    return enriched


def parse_titles_json(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if isinstance(item, str) and item.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Python bridge for movie recommendation API")
    parser.add_argument("command", choices=["recommend", "popular", "personalized", "watched", "autocomplete"])
    parser.add_argument("--query", default="")
    parser.add_argument("--top-n", type=int, default=18)
    parser.add_argument("--count", type=int, default=18)
    parser.add_argument("--per-section", type=int, default=12)
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--titles-json", default="[]")

    args = parser.parse_args()

    if args.command == "recommend":
        movie_name = args.query.strip()
        payload = {
            "movie_name": movie_name,
            "is_filter": _parse_filter_query(movie_name) is not None,
            "recommendations": attach_posters(get_recommendations(movie_name, top_n=args.top_n)),
        }
    elif args.command == "popular":
        payload = {"movies": attach_posters(get_popular_movies(args.count))}
    elif args.command == "personalized":
        titles = parse_titles_json(args.titles_json)
        sections = get_personalized_sections(titles, per_section=args.per_section)
        for section in sections:
            section["movies"] = attach_posters(section.get("movies", []))
        payload = {"sections": sections}
    elif args.command == "watched":
        titles = parse_titles_json(args.titles_json)
        payload = {"movies": attach_posters(get_watched_movies(titles))}
    else:
        payload = {"suggestions": search_titles(args.query, limit=args.limit)}

    # Use ASCII-safe output to avoid Windows cp1252 stdout encoding crashes.
    print(json.dumps(payload, ensure_ascii=True))


if __name__ == "__main__":
    main()
