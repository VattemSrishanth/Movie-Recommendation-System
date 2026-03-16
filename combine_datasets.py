"""Combine all locally available movie datasets into one training-ready CSV."""

from __future__ import annotations

import os
import re

import pandas as pd

BASE_DIR = os.path.dirname(__file__)
DATASET_DIR = os.path.join(BASE_DIR, "dataset")

GLOBAL_PATH = os.path.join(DATASET_DIR, "global_movies_series_dataset.csv")
TMDB_PATH = os.path.join(DATASET_DIR, "tmdb_movies.csv")
MOVIELENS_PATH = os.path.join(DATASET_DIR, "movies.csv")
RATINGS_PATH = os.path.join(DATASET_DIR, "ratings.csv")
COMBINED_DATASET_PATH = os.path.join(DATASET_DIR, "combined_movies_dataset.csv")

TARGET_MOVIE_COUNT = 23_000

LANGUAGE_CODE_MAP = {
    "en": "English",
    "hi": "Hindi",
    "te": "Telugu",
    "ta": "Tamil",
    "ml": "Malayalam",
    "kn": "Kannada",
    "bn": "Bengali",
    "mr": "Marathi",
    "gu": "Gujarati",
    "pa": "Punjabi",
    "ur": "Urdu",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "it": "Italian",
    "pt": "Portuguese",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese",
    "ru": "Russian",
    "ar": "Arabic",
    "tr": "Turkish",
    "th": "Thai",
    "sv": "Swedish",
    "da": "Danish",
    "no": "Norwegian",
    "nl": "Dutch",
    "pl": "Polish",
    "cs": "Czech",
    "ro": "Romanian",
    "hu": "Hungarian",
    "fi": "Finnish",
    "el": "Greek",
    "he": "Hebrew",
    "id": "Indonesian",
    "ms": "Malay",
    "vi": "Vietnamese",
    "uk": "Ukrainian",
}

STANDARD_COLUMNS = [
    "source",
    "source_id",
    "title",
    "display_title",
    "year",
    "release_date",
    "original_language",
    "language",
    "language_name",
    "genres",
    "keywords",
    "overview",
    "poster_url",
    "vote_average",
    "vote_count",
    "popularity",
    "media_type",
    "content",
]

_YEAR_RE = re.compile(r"\((\d{4})\)\s*$")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def _safe_string(series: pd.Series | object) -> pd.Series:
    if isinstance(series, pd.Series):
        return series.fillna("").astype(str).str.strip()
    return pd.Series(dtype="object")


def _extract_year_from_title(title: str) -> str:
    match = _YEAR_RE.search(title or "")
    return match.group(1) if match else ""


def _normalise_title(title: str) -> str:
    lowered = str(title).strip().lower()
    lowered = _YEAR_RE.sub("", lowered)
    lowered = _NON_ALNUM_RE.sub(" ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def _score_metadata(frame: pd.DataFrame) -> pd.Series:
    has_overview = frame["overview"].str.len().gt(0).astype(int) * 5
    has_poster = frame["poster_url"].str.len().gt(0).astype(int) * 3
    has_keywords = frame["keywords"].str.len().gt(0).astype(int) * 2
    has_language = frame["language_name"].str.len().gt(0).astype(int)
    source_bonus = frame["source"].map({"global": 3, "tmdb": 2, "movielens": 1}).fillna(0)
    return has_overview + has_poster + has_keywords + has_language + source_bonus


def _finalise_frame(frame: pd.DataFrame, source_name: str) -> pd.DataFrame:
    frame = frame.copy()

    for column in STANDARD_COLUMNS:
        if column not in frame.columns:
            frame[column] = ""

    for column in [
        "source",
        "source_id",
        "title",
        "display_title",
        "year",
        "release_date",
        "original_language",
        "language",
        "language_name",
        "genres",
        "keywords",
        "overview",
        "poster_url",
        "media_type",
        "content",
    ]:
        frame[column] = _safe_string(frame[column])

    for column in ["vote_average", "vote_count", "popularity"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0)

    frame["source"] = source_name
    frame["title"] = frame["title"].replace("", pd.NA)
    frame["title"] = frame["title"].fillna(frame["display_title"])
    frame["display_title"] = frame["display_title"].replace("", pd.NA)
    frame["display_title"] = frame["display_title"].fillna(frame["title"])
    frame["year"] = frame["year"].replace("", pd.NA)
    frame["year"] = frame["year"].fillna(frame["release_date"].str.extract(r"(\d{4})", expand=False).fillna(""))
    frame["language_name"] = frame["language_name"].replace("", pd.NA)
    frame["language_name"] = frame["language_name"].fillna(
        frame["language"].str.lower().map(LANGUAGE_CODE_MAP).fillna("")
    )
    frame["language_name"] = frame["language_name"].replace("", "Unknown")
    frame["media_type"] = frame["media_type"].replace("", "movie")
    frame["content"] = frame["content"].replace("", pd.NA)
    frame["content"] = frame["content"].fillna(
        (frame["genres"].str.replace("|", " ", regex=False) + " " + frame["overview"]).str.strip()
    )

    return frame[STANDARD_COLUMNS]


def _load_global_frame() -> pd.DataFrame | None:
    if not os.path.exists(GLOBAL_PATH):
        return None

    frame = pd.read_csv(GLOBAL_PATH)
    frame["source_id"] = frame.get("id", "")
    frame["display_title"] = frame.get("title", "")
    frame["year"] = _safe_string(frame.get("release_date", "")).str.extract(r"(\d{4})", expand=False).fillna("")
    frame["release_date"] = frame.get("release_date", "")
    frame["original_language"] = frame.get("language", "")
    frame["language_name"] = _safe_string(frame.get("language", "")).str.lower().map(LANGUAGE_CODE_MAP).fillna("")
    frame["keywords"] = ""
    frame["vote_average"] = frame.get("rating", 0)
    frame["vote_count"] = 0
    return _finalise_frame(frame, "global")


def _load_tmdb_frame() -> pd.DataFrame | None:
    if not os.path.exists(TMDB_PATH):
        return None

    frame = pd.read_csv(TMDB_PATH)
    frame["source_id"] = frame.get("tmdb_id", "")
    frame["release_date"] = _safe_string(frame.get("year", ""))
    frame["language"] = frame.get("original_language", "")
    frame["media_type"] = "movie"
    frame["content"] = (
        _safe_string(frame.get("genres", "")).str.replace("|", " ", regex=False)
        + " "
        + _safe_string(frame.get("keywords", "")).str.replace("_", " ", regex=False)
        + " "
        + _safe_string(frame.get("overview", ""))
    ).str.strip()
    return _finalise_frame(frame, "tmdb")


def _load_movielens_frame() -> pd.DataFrame | None:
    if not os.path.exists(MOVIELENS_PATH):
        return None

    frame = pd.read_csv(MOVIELENS_PATH)
    if os.path.exists(RATINGS_PATH):
        ratings = pd.read_csv(RATINGS_PATH)
        vote_stats = ratings.groupby("movieId")["rating"].agg(vote_average="mean", vote_count="count").reset_index()
        frame = frame.merge(vote_stats, on="movieId", how="left")

    raw_title = _safe_string(frame.get("title", ""))
    frame["source_id"] = frame.get("movieId", "")
    frame["display_title"] = raw_title.str.replace(r"\s*\(\d{4}\)\s*$", "", regex=True)
    frame["year"] = raw_title.apply(_extract_year_from_title)
    frame["release_date"] = frame["year"]
    frame["title"] = raw_title
    frame["original_language"] = ""
    frame["language"] = ""
    frame["language_name"] = "Unknown"
    frame["keywords"] = ""
    frame["overview"] = ""
    frame["poster_url"] = ""
    frame["popularity"] = pd.to_numeric(frame.get("vote_count", 0), errors="coerce").fillna(0)
    frame["media_type"] = "movie"
    frame["content"] = _safe_string(frame.get("genres", "")).str.replace("|", " ", regex=False)
    return _finalise_frame(frame, "movielens")


def build_combined_dataset(save: bool = True) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for loader in (_load_global_frame, _load_tmdb_frame, _load_movielens_frame):
        frame = loader()
        if frame is not None and not frame.empty:
            frames.append(frame)

    if not frames:
        raise FileNotFoundError("No source datasets found in dataset/.")

    combined = pd.concat(frames, ignore_index=True)
    combined["_title_key"] = combined["display_title"].apply(_normalise_title)
    combined["_year_key"] = combined["year"].astype(str).str.extract(r"(\d{4})", expand=False).fillna("")
    combined["_dedupe_key"] = combined["_title_key"] + "::" + combined["_year_key"]
    combined["_metadata_score"] = _score_metadata(combined)

    combined = combined.sort_values(
        by=["_metadata_score", "vote_count", "vote_average", "popularity"],
        ascending=[False, False, False, False],
    )
    raw_total = len(combined)
    combined = combined.drop_duplicates(subset=["_dedupe_key", "media_type"], keep="first").reset_index(drop=True)
    combined = combined.drop(columns=["_title_key", "_year_key", "_dedupe_key", "_metadata_score"])

    if save:
        os.makedirs(DATASET_DIR, exist_ok=True)
        combined.to_csv(COMBINED_DATASET_PATH, index=False)

    print(f"Combined raw rows: {raw_total}")
    print(f"Combined unique rows: {len(combined)}")
    if len(combined) < TARGET_MOVIE_COUNT:
        print(
            "Warning: combined dataset is below the 23000-movie target. "
            f"Current unique total is {len(combined)}. Add more source rows or rebuild TMDB data with a larger export."
        )
    else:
        print(f"Target reached: {len(combined)} >= {TARGET_MOVIE_COUNT}")

    return combined


def main() -> None:
    dataset = build_combined_dataset(save=True)
    print(f"Saved combined dataset to: {COMBINED_DATASET_PATH}")
    print(f"Final row count: {len(dataset)}")


if __name__ == "__main__":
    main()