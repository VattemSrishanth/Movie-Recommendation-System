"""
download_dataset.py
-------------------
Build a multilingual movie dataset from TMDB for content-based recommendation.

Included languages:
    en - Hollywood / English movies
    te - Telugu
    ta - Tamil
    hi - Hindi

The script fetches genres, movie details, posters, overviews, and keywords,
then stores a compact CSV that train_model.py can use directly.

Run once before training:
    set TMDB_API_KEY=your_key_here
    python download_dataset.py
"""

from __future__ import annotations

import os
import time
from typing import Any

import pandas as pd
import requests

from env_loader import load_env_file

load_env_file()

BASE_DIR = os.path.dirname(__file__)
DEST_DIR = os.path.join(BASE_DIR, "dataset")
OUTPUT_PATH = os.path.join(DEST_DIR, "tmdb_movies.csv")
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "").strip()

BASE_URL = "https://api.themoviedb.org/3"
DISCOVER_URL = f"{BASE_URL}/discover/movie"
GENRES_URL = f"{BASE_URL}/genre/movie/list"
KEYWORDS_URL = f"{BASE_URL}/movie/{{movie_id}}/keywords"
IMAGE_BASE = "https://image.tmdb.org/t/p/w500"

LANGUAGES = {
    "en": "English",
    "te": "Telugu",
    "ta": "Tamil",
    "hi": "Hindi",
}
PAGES_PER_LANGUAGE = 5


def require_api_key() -> None:
    """Fail early with a clear message if the TMDB key is missing."""
    if TMDB_API_KEY:
        return

    raise SystemExit(
        "TMDB_API_KEY is not set. Create a TMDB API key and set it before running "
        "download_dataset.py."
    )


def tmdb_get(url: str, **params: Any) -> dict[str, Any]:
    """Call TMDB and return the JSON body as a dictionary."""
    response = requests.get(
        url,
        params={"api_key": TMDB_API_KEY, **params},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("TMDB returned an unexpected response shape.")
    return payload


def fetch_genre_map() -> dict[int, str]:
    """Fetch the TMDB movie genre list once and index it by genre id."""
    payload = tmdb_get(GENRES_URL, language="en-US")
    genre_items = payload.get("genres", [])
    genre_map: dict[int, str] = {}

    if isinstance(genre_items, list):
        for item in genre_items:
            if not isinstance(item, dict):
                continue
            genre_id = item.get("id")
            genre_name = item.get("name")
            if isinstance(genre_id, int) and isinstance(genre_name, str):
                genre_map[genre_id] = genre_name

    return genre_map


def fetch_keywords(movie_id: int) -> str:
    """Fetch keywords for a movie and return them as a space-separated string."""
    payload = tmdb_get(KEYWORDS_URL.format(movie_id=movie_id))
    keyword_items = payload.get("keywords", [])

    names: list[str] = []
    if isinstance(keyword_items, list):
        for item in keyword_items:
            if not isinstance(item, dict):
                continue
            keyword = item.get("name")
            if isinstance(keyword, str) and keyword.strip():
                names.append(keyword.strip().replace(" ", "_"))

    return " ".join(names)


def fetch_movies_for_language(language_code: str, genre_map: dict[int, str]) -> list[dict[str, Any]]:
    """Fetch a set of popular movies for one language from TMDB discover."""
    movies: list[dict[str, Any]] = []

    for page in range(1, PAGES_PER_LANGUAGE + 1):
        payload = tmdb_get(
            DISCOVER_URL,
            include_adult="false",
            include_video="false",
            language="en-US",
            page=page,
            sort_by="popularity.desc",
            with_original_language=language_code,
            vote_count_gte=40,
        )
        results = payload.get("results", [])
        if not isinstance(results, list):
            continue

        print(f"Fetched page {page} for language '{language_code}'")

        for item in results:
            if not isinstance(item, dict):
                continue

            movie_id = item.get("id")
            title = item.get("title") or item.get("name")
            overview = item.get("overview") or ""
            release_date = item.get("release_date") or ""
            genre_ids = item.get("genre_ids", [])
            poster_path = item.get("poster_path") or ""
            vote_average = item.get("vote_average") or 0.0
            vote_count = item.get("vote_count") or 0
            popularity = item.get("popularity") or 0.0

            if not isinstance(movie_id, int) or not isinstance(title, str) or not title.strip():
                continue

            genres = []
            if isinstance(genre_ids, list):
                for genre_id in genre_ids:
                    if isinstance(genre_id, int) and genre_id in genre_map:
                        genres.append(genre_map[genre_id])

            keywords = fetch_keywords(movie_id)
            year = release_date[:4] if isinstance(release_date, str) and len(release_date) >= 4 else ""
            full_title = f"{title} ({year})" if year else title
            poster_url = f"{IMAGE_BASE}{poster_path}" if isinstance(poster_path, str) and poster_path else ""

            movies.append(
                {
                    "tmdb_id": movie_id,
                    "title": full_title,
                    "display_title": title,
                    "year": year,
                    "original_language": language_code,
                    "language_name": LANGUAGES.get(language_code, language_code),
                    "genres": "|".join(genres),
                    "keywords": keywords,
                    "overview": overview,
                    "poster_url": poster_url,
                    "vote_average": float(vote_average),
                    "vote_count": int(vote_count),
                    "popularity": float(popularity),
                }
            )

            time.sleep(0.05)

    return movies


def build_dataset() -> pd.DataFrame:
    """Fetch multilingual TMDB movies and return a de-duplicated dataframe."""
    require_api_key()
    os.makedirs(DEST_DIR, exist_ok=True)

    genre_map = fetch_genre_map()
    all_movies: list[dict[str, Any]] = []

    for language_code in LANGUAGES:
        all_movies.extend(fetch_movies_for_language(language_code, genre_map))

    movies = pd.DataFrame(all_movies)
    movies = movies.drop_duplicates(subset=["tmdb_id"]).copy()
    movies = movies[movies["genres"].fillna("") != ""]
    movies["overview"] = movies["overview"].fillna("")
    movies["keywords"] = movies["keywords"].fillna("")
    movies["year"] = movies["year"].fillna("")
    movies.reset_index(drop=True, inplace=True)
    return movies


def main() -> None:
    movies = build_dataset()
    movies.to_csv(OUTPUT_PATH, index=False)
    print(f"Saved {len(movies)} TMDB movies to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
