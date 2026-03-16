"""
train_model.py
--------------
Load the TMDB movie dataset, preprocess text with NLP techniques
(tokenization, stopword removal, stemming), build TF-IDF vectors,
train a K-Nearest Neighbours model, and save pickle files for the Flask app.

Usage:
    python train_model.py
"""

import os
import pickle
import re
import string

import nltk
import pandas as pd
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer
from nltk.tokenize import word_tokenize
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neighbors import NearestNeighbors

from combine_datasets import COMBINED_DATASET_PATH, build_combined_dataset

# Download required NLTK data (only on first run)
nltk.download("punkt", quiet=True)
nltk.download("punkt_tab", quiet=True)
nltk.download("stopwords", quiet=True)

# ── paths ────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(__file__)
DATASET_DIR = os.path.join(BASE_DIR, "dataset")
MODEL_DIR = os.path.join(BASE_DIR, "model")
MOVIES_PKL = os.path.join(MODEL_DIR, "movies.pkl")
SIMILARITY_PKL = os.path.join(MODEL_DIR, "similarity.pkl")

# ── NLP helpers ──────────────────────────────────────────────────────────
_stemmer = PorterStemmer()
_stop_words = set(stopwords.words("english"))
_punct_re = re.compile(f"[{re.escape(string.punctuation)}]")


def _clean_and_stem(text: str) -> str:
    """Lowercase, remove punctuation, tokenize, remove stopwords, and stem."""
    text = text.lower()
    text = _punct_re.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    tokens = word_tokenize(text)
    tokens = [_stemmer.stem(w) for w in tokens if w not in _stop_words and len(w) > 1]
    return " ".join(tokens)


# ── pipeline stages ─────────────────────────────────────────────────────

def load_data() -> pd.DataFrame:
    """Build or reload the unified combined dataset used for training."""
    df = build_combined_dataset(save=True)
    print(f"Training source: {COMBINED_DATASET_PATH}")
    print(f"Rows available for training: {len(df)}")
    return df


# ISO 639-1 code → full language name
_LANG_CODE_MAP = {
    "en": "English", "hi": "Hindi", "te": "Telugu", "ta": "Tamil",
    "ml": "Malayalam", "kn": "Kannada", "bn": "Bengali", "mr": "Marathi",
    "gu": "Gujarati", "pa": "Punjabi", "ur": "Urdu",
    "fr": "French", "de": "German", "es": "Spanish", "it": "Italian",
    "pt": "Portuguese", "ja": "Japanese", "ko": "Korean", "zh": "Chinese",
    "ru": "Russian", "ar": "Arabic", "tr": "Turkish", "th": "Thai",
    "sv": "Swedish", "da": "Danish", "no": "Norwegian", "nl": "Dutch",
    "pl": "Polish", "cs": "Czech", "ro": "Romanian", "hu": "Hungarian",
    "fi": "Finnish", "el": "Greek", "he": "Hebrew", "id": "Indonesian",
    "ms": "Malay", "vi": "Vietnamese", "uk": "Ukrainian",
}


def preprocess(df: pd.DataFrame) -> pd.DataFrame:
    """Clean columns, build a combined 'tags' column, and apply NLP stemming."""
    df = df.copy()

    # ── normalise column names across CSV variants ───────────────────────
    if "rating" in df.columns and "vote_average" not in df.columns:
        df.rename(columns={"rating": "vote_average"}, inplace=True)

    # ── build a unified language_name from all available sources ─────────
    # Priority: language_name (TMDB) → language code → original_language code
    if "language_name" not in df.columns:
        df["language_name"] = ""
    df["language_name"] = df["language_name"].fillna("")

    # Map ISO codes to names for rows missing language_name
    for code_col in ["language", "original_language"]:
        if code_col in df.columns:
            mask = df["language_name"].str.strip() == ""
            df.loc[mask, "language_name"] = (
                df.loc[mask, code_col]
                .fillna("")
                .str.strip()
                .str.lower()
                .map(_LANG_CODE_MAP)
                .fillna("")
            )

    # ── normalise media_type ─────────────────────────────────────────────
    if "media_type" not in df.columns:
        df["media_type"] = "movie"
    df["media_type"] = df["media_type"].fillna("movie").str.strip().str.lower()
    df.loc[df["media_type"] == "", "media_type"] = "movie"

    # ── fill missing values ──────────────────────────────────────────────
    for col in ["title", "genres", "overview", "poster_url"]:
        if col in df.columns:
            df[col] = df[col].fillna("")
    if "keywords" not in df.columns:
        df["keywords"] = ""
    else:
        df["keywords"] = df["keywords"].fillna("")
    if "display_title" not in df.columns:
        df["display_title"] = df["title"]
    else:
        df["display_title"] = df["display_title"].fillna(df["title"])

    df["vote_average"] = pd.to_numeric(df.get("vote_average", 0), errors="coerce").fillna(0.0)
    df["popularity"] = pd.to_numeric(df.get("popularity", 0), errors="coerce").fillna(0.0)
    df["poster_url"] = df["poster_url"].fillna("")

    # ── drop rows that have NO useful text at all ────────────────────────
    has_genres = df["genres"].str.strip().str.len() > 0
    has_overview = df["overview"].str.strip().str.len() > 0
    df = df[has_genres | has_overview].copy()

    # ── build the combined tags column ───────────────────────────────────
    genres_clean = df["genres"].str.replace("|", " ", regex=False)
    keywords_clean = df["keywords"].str.replace("_", " ", regex=False)
    overview_clean = df["overview"].fillna("")
    lang_text = df["language_name"].fillna("")
    type_text = df["media_type"].fillna("movie")
    title_text = df["display_title"].fillna(df["title"]) 
    # Include language (repeated for stronger signal) and media_type in tags
    raw_tags = (title_text + " " + genres_clean + " " + keywords_clean + " " + overview_clean
                + " " + lang_text + " " + lang_text + " " + type_text).str.lower()

    print("Applying NLP preprocessing (tokenize → stopwords → stemming)...")
    df["tags"] = raw_tags.apply(_clean_and_stem)

    # Drop rows where tags ended up empty after cleaning
    df = df[df["tags"].str.strip() != ""]

    df.reset_index(drop=True, inplace=True)

    lang_dist = df["language_name"].value_counts()
    print(f"After cleaning: {len(df)} movies remain")
    print(f"Language distribution:\n{lang_dist.head(10)}")
    return df


def build_knn_model(df: pd.DataFrame):
    """TF-IDF vectorize the tags column and train a KNN model.

    Uses sklearn NearestNeighbors with cosine distance. The fitted model
    stores the TF-IDF vectors internally and uses a ball-tree structure
    for fast k-neighbour lookups, scaling well to 50k+ movies.
    """
    tfidf = TfidfVectorizer(max_features=15000, stop_words="english")
    tfidf_matrix = tfidf.fit_transform(df["tags"])
    print(f"TF-IDF matrix shape: {tfidf_matrix.shape}")

    # Train KNN model — n_neighbors capped at dataset size
    k = min(121, len(df))  # enough headroom for wider recommendation lists
    knn = NearestNeighbors(n_neighbors=k, metric="cosine", algorithm="brute")
    knn.fit(tfidf_matrix)
    print(f"KNN model trained  (k={k}, metric=cosine)")

    return knn, tfidf_matrix


KNN_PKL = os.path.join(MODEL_DIR, "knn_model.pkl")
TFIDF_PKL = os.path.join(MODEL_DIR, "tfidf_matrix.pkl")


def save_model(df: pd.DataFrame, knn_model, tfidf_matrix):
    """Save movies DataFrame, fitted KNN model, and TF-IDF matrix."""
    os.makedirs(MODEL_DIR, exist_ok=True)

    with open(MOVIES_PKL, "wb") as f:
        pickle.dump(df, f)
    print(f"Saved movies     → {MOVIES_PKL}  ({os.path.getsize(MOVIES_PKL) / 1024 / 1024:.1f} MB)")

    with open(KNN_PKL, "wb") as f:
        pickle.dump(knn_model, f)
    print(f"Saved KNN model  → {KNN_PKL}  ({os.path.getsize(KNN_PKL) / 1024 / 1024:.1f} MB)")

    with open(TFIDF_PKL, "wb") as f:
        pickle.dump(tfidf_matrix, f)
    print(f"Saved TF-IDF     → {TFIDF_PKL}  ({os.path.getsize(TFIDF_PKL) / 1024 / 1024:.1f} MB)")


def main():
    print("=" * 50)
    print("  Training Movie Recommendation Model")
    print("=" * 50)

    df = load_data()
    df = preprocess(df)
    knn_model, tfidf_matrix = build_knn_model(df)
    save_model(df, knn_model, tfidf_matrix)

    print("\nDone! Run the Flask app with:  python app.py")


if __name__ == "__main__":
    main()
