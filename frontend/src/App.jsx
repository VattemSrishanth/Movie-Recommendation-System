import { useEffect, useMemo, useState } from "react";

const TOKEN_KEY = "movie_jwt_token";

const QUICK_FILTERS = [
  { label: "All Titles", query: "" },
  { label: "🔥 Trending", query: "trending" },
  { label: "Telugu Cinema", query: "Telugu" },
  { label: "Hindi Movies", query: "Hindi" },
  { label: "Tamil Cinema", query: "Tamil" },
  { label: "Sci-Fi & Space", query: "Science Fiction" },
  { label: "Action Blockbusters", query: "Action" },
  { label: "Crime & Mystery", query: "Mystery" }
];

function PosterCard({ movie, onToggleWatch, watchedSet }) {
  const isWatched = watchedSet.has(movie.title);
  const displayTitle = movie.display_title || movie.title;
  const ratingScore = movie.score ? (movie.score > 1 ? movie.score : (movie.score * 10).toFixed(1)) : "8.6";

  return (
    <article className="movie-card">
      <div className="poster-wrapper">
        <img
          className="poster"
          src={movie.poster_url}
          alt={displayTitle}
          loading="lazy"
          onError={(e) => {
            e.target.src = `https://placehold.co/500x750/141418/FFFFFF?text=${encodeURIComponent(displayTitle)}`;
          }}
        />
        <div className="floating-badge">★ {ratingScore}</div>
        <div className="poster-overlay">
          <span className="floating-badge" style={{ position: "static", alignSelf: "flex-start", marginBottom: "0.4rem" }}>
            {movie.year || "2026"}
          </span>
        </div>
      </div>
      <div className="movie-meta">
        <h3 className="movie-title" title={displayTitle}>{displayTitle}</h3>
        <div className="movie-subtext">
          <span>{movie.year || "2026"}</span>
          <span>•</span>
          <span style={{ color: "#e50914", fontWeight: 600 }}>{movie.language || "Multilingual"}</span>
        </div>
        {movie.genres && (
          <div className="genre-tag" title={movie.genres.replace(/\|/g, ", ")}>
            {movie.genres.split("|").slice(0, 2).join(" • ")}
          </div>
        )}
        <button
          className={`btn-watch ${isWatched ? "watched" : ""}`}
          onClick={() => onToggleWatch(movie.title, isWatched)}
        >
          {isWatched ? "✓ In Watchlist" : "+ Add to Watchlist"}
        </button>
      </div>
    </article>
  );
}

async function api(path, options = {}, token = "") {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(path, {
    headers,
    ...options,
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || "Request failed");
  }
  return data;
}

export default function App() {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY) || "");
  const [user, setUser] = useState(null);
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [authMode, setAuthMode] = useState("login");
  const [authUsername, setAuthUsername] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authLoading, setAuthLoading] = useState(false);
  const [activeFilter, setActiveFilter] = useState("");

  const [query, setQuery] = useState("");
  const [popular, setPopular] = useState([]);
  const [personalized, setPersonalized] = useState([]);
  const [recommendations, setRecommendations] = useState([]);
  const [suggestions, setSuggestions] = useState([]);
  const [watched, setWatched] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const watchedSet = useMemo(() => new Set(watched.map((m) => m.title)), [watched]);

  const persistToken = (nextToken) => {
    setToken(nextToken);
    if (nextToken) {
      localStorage.setItem(TOKEN_KEY, nextToken);
    } else {
      localStorage.removeItem(TOKEN_KEY);
    }
  };

  const refreshHomeData = async (activeToken = token) => {
    const popularData = await api("/api/popular");
    setPopular(popularData.movies || []);

    if (!activeToken) {
      setPersonalized([]);
      setWatched([]);
      return;
    }

    try {
      const [personalizedData, watchedData] = await Promise.all([
        api("/api/personalized", {}, activeToken),
        api("/api/watched", {}, activeToken),
      ]);
      setPersonalized(personalizedData.sections || []);
      setWatched(watchedData.movies || []);
    } catch {
      // Ignore background personalized sync errors
    }
  };

  useEffect(() => {
    const load = async () => {
      setError("");
      try {
        if (token) {
          const meData = await api("/api/auth/me", {}, token);
          setUser(meData.user || null);
          await refreshHomeData(token);
        } else {
          setUser(null);
          await refreshHomeData("");
        }
      } catch (err) {
        persistToken("");
        setUser(null);
        setPersonalized([]);
        setWatched([]);
        await refreshHomeData("");
      }
    };

    load().catch((err) => setError(err.message));
  }, [token]);

  useEffect(() => {
    const timer = setTimeout(async () => {
      if (!query.trim()) {
        setSuggestions([]);
        return;
      }
      try {
        const data = await api(`/api/autocomplete?q=${encodeURIComponent(query)}`);
        setSuggestions(data.suggestions || []);
      } catch {
        setSuggestions([]);
      }
    }, 180);

    return () => clearTimeout(timer);
  }, [query]);

  const executeRecommendation = async (searchTarget) => {
    const term = (searchTarget || query).trim();
    if (!term) return;

    setLoading(true);
    setError("");

    try {
      const data = await api("/api/recommend", {
        method: "POST",
        body: JSON.stringify({ movie_name: term, top_n: 18 }),
      }, token);
      setRecommendations(data.recommendations || []);
      const resultsSection = document.getElementById("results-view");
      if (resultsSection) {
        resultsSection.scrollIntoView({ behavior: "smooth" });
      }
    } catch (err) {
      setRecommendations([]);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSearchSubmit = (event) => {
    event.preventDefault();
    executeRecommendation(query);
  };

  const handleFilterClick = (filterObj) => {
    setActiveFilter(filterObj.label);
    if (!filterObj.query) {
      setQuery("");
      setRecommendations([]);
      return;
    }
    setQuery(filterObj.query);
    executeRecommendation(filterObj.query);
  };

  const handleAuth = async (event) => {
    event.preventDefault();
    const username = authUsername.trim();
    const password = authPassword;
    if (!username || !password) {
      setError("Username and password are required");
      return;
    }

    setAuthLoading(true);
    setError("");

    try {
      const endpoint = authMode === "register" ? "/api/auth/register" : "/api/auth/login";
      const data = await api(endpoint, {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
      persistToken(data.token || "");
      setUser(data.user || null);
      setAuthPassword("");
      setAuthModalOpen(false);
      await refreshHomeData(data.token || "");
    } catch (err) {
      setError(err.message);
    } finally {
      setAuthLoading(false);
    }
  };

  const logout = () => {
    persistToken("");
    setUser(null);
    setWatched([]);
    setPersonalized([]);
  };

  const toggleWatch = async (title, isWatched) => {
    if (!token) {
      setAuthModalOpen(true);
      setError("Please sign in or create an account to save movies to your watchlist");
      return;
    }

    const endpoint = isWatched ? "/api/unwatch" : "/api/watch";
    await api(endpoint, {
      method: "POST",
      body: JSON.stringify({ title }),
    }, token);
    await refreshHomeData(token);
  };

  return (
    <div className="shell">
      {/* Top Navbar */}
      <nav className="navbar">
        <a href="/" className="brand">
          <div className="brand-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
              <rect x="2" y="2" width="20" height="20" rx="4" />
              <line x1="7" y1="2" x2="7" y2="22" />
              <line x1="17" y1="2" x2="17" y2="22" />
              <line x1="2" y1="12" x2="22" y2="12" />
              <line x1="2" y1="7" x2="7" y2="7" />
              <line x1="2" y1="17" x2="7" y2="17" />
              <line x1="17" y1="17" x2="22" y2="17" />
              <line x1="17" y1="7" x2="22" y2="7" />
            </svg>
          </div>
          <span className="brand-text">CINEMATCH</span>
          <span className="brand-badge">ML Studio</span>
        </a>

        <div className="nav-links">
          <span className="nav-item active">Discover</span>
          <span className="nav-item" onClick={() => executeRecommendation("trending")}>Trending</span>
          <span className="nav-item" onClick={() => executeRecommendation("Telugu")}>Telugu</span>
          <span className="nav-item" onClick={() => executeRecommendation("Hindi")}>Hindi</span>
          <span className="nav-item" onClick={() => executeRecommendation("Tamil")}>Tamil</span>
        </div>

        <div className="nav-actions">
          {user ? (
            <div className="user-pill">
              <div className="avatar">{user.username.charAt(0).toUpperCase()}</div>
              <span className="username">{user.username}</span>
              <button className="btn-signout" onClick={logout} title="Sign Out">✕</button>
            </div>
          ) : (
            <button className="btn-signin" onClick={() => { setError(""); setAuthModalOpen(true); }}>
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                <circle cx="12" cy="7" r="4" />
              </svg>
              Sign In
            </button>
          )}
        </div>
      </nav>

      {/* Hero Spotlight */}
      <header className="hero-spotlight">
        <div className="spotlight-content">
          <div className="badge-trending">
            <span>✨</span> #1 AI FEATURED MATCH • CONTENT-BASED KNN
          </div>
          <h1 className="spotlight-title">Interstellar (2014)</h1>
          <div className="meta-row">
            <span className="rating-badge">★ 8.9 IMDb</span>
            <span className="meta-pill">Sci-Fi • Adventure</span>
            <span className="meta-pill">English • Multilingual</span>
            <span className="meta-pill">2h 49m</span>
            <span className="meta-pill" style={{ color: "#34d399", borderColor: "rgba(52, 211, 153, 0.3)" }}>98% Match</span>
          </div>
          <p className="spotlight-desc">
            When Earth becomes uninhabitable, a team of researchers and astronauts undertake the most critical mission in human history: traveling beyond this galaxy to discover whether mankind has a future among the stars.
          </p>
          <div className="spotlight-actions">
            <button
              className="btn-primary"
              onClick={() => {
                setQuery("Interstellar");
                executeRecommendation("Interstellar");
              }}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                <polygon points="5 3 19 12 5 21 5 3" />
              </svg>
              Get AI Recommendations
            </button>
            <button
              className="btn-secondary"
              onClick={() => toggleWatch("Interstellar (2014)", watchedSet.has("Interstellar (2014)"))}
            >
              {watchedSet.has("Interstellar (2014)") ? "✓ Watchlisted" : "+ Add to Watchlist"}
            </button>
          </div>
        </div>
      </header>

      {/* Search & Filter Section */}
      <section className="search-filter-section">
        <form className="search-box" onSubmit={handleSearchSubmit}>
          <div className="search-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
          </div>
          <input
            className="search-input"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search movie title, director, genre or try: 'Interstellar', 'Telugu Action', 'Hindi Drama'..."
          />
          <button type="submit" className="btn-recommend" disabled={loading}>
            {loading ? "Matching..." : "Recommend"}
          </button>
        </form>

        {/* Quick Filter Pills */}
        <div className="filter-pills">
          {QUICK_FILTERS.map((filter) => (
            <button
              key={filter.label}
              className={`pill ${activeFilter === filter.label ? "active" : ""}`}
              onClick={() => handleFilterClick(filter)}
            >
              {filter.label}
            </button>
          ))}
        </div>

        {/* Autocomplete Dropdown */}
        {suggestions.length > 0 && (
          <div className="suggestions-dropdown">
            <span style={{ fontSize: "0.76rem", color: "#9ba1b0", alignSelf: "center", marginRight: "0.25rem" }}>
              Quick Matches:
            </span>
            {suggestions.map((item) => (
              <button
                key={item}
                className="suggestion-chip"
                onClick={() => {
                  setQuery(item);
                  executeRecommendation(item);
                }}
              >
                {item}
              </button>
            ))}
          </div>
        )}

        {error && <div className="error" style={{ marginTop: "1rem" }}>{error}</div>}
      </section>

      {/* Search Recommendations Results */}
      {recommendations.length > 0 && (
        <section id="results-view" className="catalog-section">
          <div className="section-header">
            <div>
              <h2 className="section-title">
                <span>🎯</span> Recommended for "{query}"
              </h2>
              <p className="section-desc">Computed using TF-IDF metadata vectorization and K-Nearest Neighbors</p>
            </div>
            <span className="section-count">{recommendations.length} Matched Titles</span>
          </div>
          <div className="grid">
            {recommendations.map((movie) => (
              <PosterCard
                key={`${movie.title}-${movie.year || "na"}`}
                movie={movie}
                onToggleWatch={toggleWatch}
                watchedSet={watchedSet}
              />
            ))}
          </div>
        </section>
      )}

      {/* For You / Personalized Section */}
      <section className="catalog-section">
        <div className="section-header">
          <div>
            <h2 className="section-title">
              <span>🍿</span> Personalized For You
            </h2>
            <p className="section-desc">Adaptive content recommendations based on your watch history</p>
          </div>
        </div>

        {!token && (
          <div style={{
            background: "rgba(255, 255, 255, 0.03)",
            border: "1px dashed var(--panel-border)",
            borderRadius: "var(--radius-md)",
            padding: "2.5rem 1.5rem",
            textAlign: "center"
          }}>
            <p style={{ color: "var(--text-muted)", fontSize: "0.95rem", marginBottom: "1rem" }}>
              Sign in and add films to your watchlist to unlock custom recommendations tailored to your taste.
            </p>
            <button className="btn-signin" onClick={() => setAuthModalOpen(true)}>
              Sign In to Unlock
            </button>
          </div>
        )}

        {token && personalized.length === 0 && (
          <p style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>
            Add a few movies to your watchlist above to generate your customized taste profile.
          </p>
        )}

        {personalized.map((section) => (
          <div key={section.title} style={{ marginBottom: "2rem" }}>
            <h3 style={{ fontSize: "1.15rem", fontWeight: 700, marginBottom: "0.25rem" }}>{section.title}</h3>
            <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", marginBottom: "1rem" }}>{section.reason}</p>
            <div className="grid">
              {section.movies.map((movie) => (
                <PosterCard
                  key={`${section.title}-${movie.title}`}
                  movie={movie}
                  onToggleWatch={toggleWatch}
                  watchedSet={watchedSet}
                />
              ))}
            </div>
          </div>
        ))}
      </section>

      {/* Popular Right Now */}
      <section className="catalog-section">
        <div className="section-header">
          <div>
            <h2 className="section-title">
              <span>🔥</span> Popular & Trending
            </h2>
            <p className="section-desc">Highest scoring films across multilingual datasets</p>
          </div>
          <span className="section-count">{popular.length} Titles</span>
        </div>
        <div className="grid">
          {popular.map((movie) => (
            <PosterCard
              key={`popular-${movie.title}`}
              movie={movie}
              onToggleWatch={toggleWatch}
              watchedSet={watchedSet}
            />
          ))}
        </div>
      </section>

      {/* Clean Auth Modal */}
      {authModalOpen && (
        <div className="modal-overlay" onClick={() => setAuthModalOpen(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <button className="modal-close" onClick={() => setAuthModalOpen(false)}>✕</button>
            <h2 className="modal-title">{authMode === "login" ? "Welcome Back" : "Create Account"}</h2>
            <p className="modal-sub">
              {authMode === "login" ? "Sign in to access your personal watchlist & AI recommendations" : "Join CineMatch to get personalized movie recommendations"}
            </p>

            <form onSubmit={handleAuth} className="auth-form-inputs">
              <input
                className="input-field"
                value={authUsername}
                onChange={(e) => setAuthUsername(e.target.value)}
                placeholder="Username"
                autoFocus
              />
              <input
                className="input-field"
                type="password"
                value={authPassword}
                onChange={(e) => setAuthPassword(e.target.value)}
                placeholder="Password"
              />
              <button type="submit" className="btn-submit-auth" disabled={authLoading}>
                {authLoading ? "Authenticating..." : authMode === "login" ? "Sign In" : "Register"}
              </button>
            </form>

            <div className="auth-toggle-mode">
              {authMode === "login" ? "Don't have an account?" : "Already have an account?"}
              <button
                type="button"
                className="auth-toggle-btn"
                onClick={() => setAuthMode(authMode === "login" ? "register" : "login")}
              >
                {authMode === "login" ? "Register now" : "Log in"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Footer */}
      <footer className="footer">
        <div>
          <strong>CINEMATCH</strong> • Machine Learning Movie Recommendation Studio
        </div>
        <div className="footer-tags">
          <span className="footer-pill">Scikit-Learn KNN</span>
          <span className="footer-pill">TF-IDF Vectorization</span>
          <span className="footer-pill">Cosine Distance</span>
          <span className="footer-pill">Node.js Express API</span>
          <span className="footer-pill">React 18 SPA</span>
        </div>
      </footer>
    </div>
  );
}
