"""
dataset_builder.py
------------------
Collect a focused multilingual dataset of popular movies from TMDB and save it
as a CSV suitable for machine learning training.

The script iterates across:
    - original languages
    - release years
    - TMDB discover pages

It stops when the cleaned dataset reaches roughly the configured target size.
"""

from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Any

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from env_loader import load_env_file

load_env_file()

BASE_DIR = os.path.dirname(__file__)
DATASET_DIR = os.path.join(BASE_DIR, "dataset")
OUTPUT_PATH = os.path.join(DATASET_DIR, "global_movies_series_dataset.csv")

API_KEY = os.getenv("TMDB_API_KEY", "YOUR_API_KEY").strip()
BASE_URL = "https://api.themoviedb.org/3"
DISCOVER_ENDPOINTS = {
    "movie": f"{BASE_URL}/discover/movie",
}
GENRE_LIST_URL = f"{BASE_URL}/genre/movie/list"
POSTER_BASE_URL = "https://image.tmdb.org/t/p/w500"

LANGUAGES = ["en", "hi", "te"]
START_YEAR = 1990
CURRENT_YEAR = datetime.now().year
MAX_PAGES_PER_QUERY = 500
PAGE_SIZE = 20
TARGET_DATASET_SIZE = 10_000
RAW_COLLECTION_BUFFER = 12_000
REQUEST_DELAY_SECONDS = 0.12
REQUEST_TIMEOUT_SECONDS = 30
MIN_VOTE_COUNT = 20


def require_api_key() -> None:
    if API_KEY and API_KEY != "YOUR_API_KEY":
        return

    raise SystemExit(
        "TMDB API key is missing. Set TMDB_API_KEY in your environment or .env file before running dataset_builder.py."
    )


def create_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=5,
        connect=5,
        read=5,
        backoff_factor=1.0,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def tmdb_get(session: requests.Session, url: str, **params: Any) -> dict[str, Any] | None:
    try:
        response = session.get(
            url,
            params={"api_key": API_KEY, **params},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict):
            return payload
    except requests.RequestException as exc:
        print(f"Request failed for {url}: {exc}")
    except ValueError as exc:
        print(f"Invalid JSON from TMDB for {url}: {exc}")
    return None


def fetch_genre_map(session: requests.Session) -> dict[int, str]:
    payload = tmdb_get(session, GENRE_LIST_URL, language="en-US")
    if not payload:
        return {}

    genre_map: dict[int, str] = {}
    genre_items = payload.get("genres", [])
    if not isinstance(genre_items, list):
        return genre_map

    for item in genre_items:
        if not isinstance(item, dict):
            continue
        genre_id = item.get("id")
        name = item.get("name")
        if isinstance(genre_id, int) and isinstance(name, str) and name.strip():
            genre_map[genre_id] = name.strip()

    return genre_map


def normalize_record(item: dict[str, Any], media_type: str, genre_map: dict[int, str]) -> dict[str, Any] | None:
    title = item.get("title") if media_type == "movie" else item.get("name")
    release_date = item.get("release_date") if media_type == "movie" else item.get("first_air_date")
    poster_path = item.get("poster_path")
    item_id = item.get("id")
    overview = item.get("overview") or ""
    original_language = item.get("original_language") or ""

    if not isinstance(item_id, int):
        return None
    if not isinstance(title, str) or not title.strip():
        return None

    poster_url = ""
    if isinstance(poster_path, str) and poster_path.strip():
        poster_url = f"{POSTER_BASE_URL}{poster_path.strip()}"

    genre_ids = item.get("genre_ids")
    if not isinstance(genre_ids, list):
        genre_ids = []
    genre_names = [genre_map[genre_id] for genre_id in genre_ids if isinstance(genre_id, int) and genre_id in genre_map]
    content = " ".join(part for part in [" ".join(genre_names), overview.strip()] if part).strip()

    return {
        "id": item_id,
        "title": title.strip(),
        "overview": overview.strip(),
        "genres": "|".join(genre_names),
        "genre_ids": "|".join(str(genre_id) for genre_id in genre_ids if isinstance(genre_id, int)),
        "content": content,
        "rating": float(item.get("vote_average") or 0.0),
        "popularity": float(item.get("popularity") or 0.0),
        "language": str(original_language).strip(),
        "poster_url": poster_url,
        "release_date": str(release_date or "").strip(),
        "media_type": media_type,
    }


def clean_dataset(records: list[dict[str, Any]]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame(
            columns=[
                "id",
                "title",
                "overview",
                "genres",
                "content",
                "language",
                "rating",
                "popularity",
                "poster_url",
                "release_date",
                "media_type",
            ]
        )

    dataset = pd.DataFrame.from_records(records)
    dataset["title"] = dataset["title"].fillna("").astype(str).str.strip()
    dataset["overview"] = dataset["overview"].fillna("").astype(str).str.strip()
    dataset["genres"] = dataset["genres"].fillna("").astype(str).str.strip()
    dataset["content"] = dataset["content"].fillna("").astype(str).str.strip()
    dataset["poster_url"] = dataset["poster_url"].fillna("").astype(str).str.strip()
    dataset["release_date"] = dataset["release_date"].fillna("").astype(str).str.strip()
    dataset["language"] = dataset["language"].fillna("").astype(str).str.strip()
    dataset["media_type"] = dataset["media_type"].fillna("").astype(str).str.strip()
    dataset["rating"] = pd.to_numeric(dataset["rating"], errors="coerce").fillna(0.0)
    dataset["popularity"] = pd.to_numeric(dataset["popularity"], errors="coerce").fillna(0.0)

    dataset = dataset.drop_duplicates(subset=["id", "media_type"])
    dataset = dataset[dataset["title"] != ""]
    dataset = dataset[dataset["overview"] != ""]
    dataset = dataset[dataset["genres"] != ""]
    dataset = dataset[dataset["poster_url"] != ""]
    dataset = dataset[
        [
            "id",
            "title",
            "overview",
            "genres",
            "content",
            "language",
            "rating",
            "popularity",
            "poster_url",
            "release_date",
            "media_type",
        ]
    ]
    dataset = dataset.sort_values(
        by=["popularity", "rating", "release_date"],
        ascending=[False, False, False],
    ).reset_index(drop=True)

    if len(dataset) > TARGET_DATASET_SIZE:
        dataset = dataset.head(TARGET_DATASET_SIZE).copy()

    return dataset


def fetch_titles() -> pd.DataFrame:
    require_api_key()
    os.makedirs(DATASET_DIR, exist_ok=True)

    session = create_session()
    genre_map = fetch_genre_map(session)
    records: list[dict[str, Any]] = []
    seen_keys: set[tuple[int, str]] = set()
    movies_collected = 0

    for media_type, endpoint in DISCOVER_ENDPOINTS.items():
        for language in LANGUAGES:
            for year in range(CURRENT_YEAR, START_YEAR - 1, -1):
                if len(records) >= RAW_COLLECTION_BUFFER:
                    cleaned = clean_dataset(records)
                    if len(cleaned) >= TARGET_DATASET_SIZE:
                        return cleaned

                page = 1
                empty_pages_in_row = 0

                while page <= MAX_PAGES_PER_QUERY:
                    params: dict[str, Any] = {
                        "sort_by": "popularity.desc",
                        "page": page,
                        "with_original_language": language,
                        "vote_count.gte": MIN_VOTE_COUNT,
                        "include_adult": "false",
                    }

                    if media_type == "movie":
                        params["primary_release_year"] = year
                    else:
                        params["first_air_date_year"] = year

                    payload = tmdb_get(session, endpoint, **params)
                    time.sleep(REQUEST_DELAY_SECONDS)

                    if not payload:
                        page += 1
                        continue

                    results = payload.get("results", [])
                    total_pages = payload.get("total_pages", 0)
                    if not isinstance(results, list) or not results:
                        empty_pages_in_row += 1
                        if empty_pages_in_row >= 2:
                            break
                        page += 1
                        continue

                    empty_pages_in_row = 0
                    valid_total_pages = total_pages if isinstance(total_pages, int) and total_pages > 0 else 1
                    effective_total_pages = min(valid_total_pages, MAX_PAGES_PER_QUERY)

                    for item in results:
                        if not isinstance(item, dict):
                            continue
                        record = normalize_record(item, media_type, genre_map)
                        if record is None:
                            continue

                        record_key = (record["id"], record["media_type"])
                        if record_key in seen_keys:
                            continue

                        seen_keys.add(record_key)
                        records.append(record)

                        movies_collected += 1

                    print(
                        f"media={media_type} language={language} year={year} page={page}/{effective_total_pages} total_titles={len(records)}"
                    )

                    if len(records) >= RAW_COLLECTION_BUFFER:
                        cleaned = clean_dataset(records)
                        if len(cleaned) >= TARGET_DATASET_SIZE:
                            return cleaned

                    if page >= effective_total_pages:
                        break

                    page += 1

    dataset = clean_dataset(records)
    final_movies = int((dataset["media_type"] == "movie").sum())
    print(f"Raw movie records collected: {movies_collected}")
    print(f"Cleaned movie records: {final_movies}")
    return dataset


def main() -> None:
    dataset = fetch_titles()
    dataset.to_csv(OUTPUT_PATH, index=False)

    total_movies = int((dataset["media_type"] == "movie").sum())
    total_size = len(dataset)

    print("Dataset build complete.")
    print(f"Total movies collected: {total_movies}")
    print(f"Total dataset size: {total_size}")
    print(f"Saved dataset to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()