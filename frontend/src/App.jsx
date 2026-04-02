import { useEffect, useMemo, useState } from "react";

const TOKEN_KEY = "movie_jwt_token";

function PosterCard({ movie, onToggleWatch, watchedSet }) {
  const isWatched = watchedSet.has(movie.title);

  return (
    <article className="movie-card">
      <img className="poster" src={movie.poster_url} alt={movie.display_title} loading="lazy" />
      <div className="movie-meta">
        <h3>{movie.display_title}</h3>
        <p>{movie.year || "Unknown year"} • {movie.language || "Unknown"}</p>
        <button className="chip" onClick={() => onToggleWatch(movie.title, isWatched)}>
          {isWatched ? "Unwatch" : "Watch"}
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
  const [authMode, setAuthMode] = useState("login");
  const [authUsername, setAuthUsername] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authLoading, setAuthLoading] = useState(false);
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

    const [personalizedData, watchedData] = await Promise.all([
      api("/api/personalized", {}, activeToken),
      api("/api/watched", {}, activeToken),
    ]);

    setPersonalized(personalizedData.sections || []);
    setWatched(watchedData.movies || []);
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
        setError(err.message);
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

  const handleSearch = async (event) => {
    event.preventDefault();
    if (!query.trim()) {
      return;
    }

    setLoading(true);
    setError("");

    try {
      const data = await api("/api/recommend", {
        method: "POST",
        body: JSON.stringify({ movie_name: query.trim(), top_n: 18 }),
      }, token);
      setRecommendations(data.recommendations || []);
    } catch (err) {
      setRecommendations([]);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleAuth = async (event) => {
    event.preventDefault();
    const username = authUsername.trim();
    const password = authPassword;
    if (!username || !password) {
      setError("username and password are required");
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
      setError("Please login to save watch history");
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
      <header className="hero">
        <p className="eyebrow">Hybrid ML Stack</p>
        <h1>Movie Recommender Studio</h1>
        <p className="subtitle">
          Notebook-trained model, JavaScript API, and a React dashboard on top of your existing recommender.
        </p>

        <div className="auth-panel">
          {user ? (
            <div className="auth-row">
              <span>Signed in as <strong>{user.username}</strong></span>
              <button className="secondary" onClick={logout}>Logout</button>
            </div>
          ) : (
            <form className="auth-form" onSubmit={handleAuth}>
              <div className="auth-tabs">
                <button type="button" className={authMode === "login" ? "tab active" : "tab"} onClick={() => setAuthMode("login")}>Login</button>
                <button type="button" className={authMode === "register" ? "tab active" : "tab"} onClick={() => setAuthMode("register")}>Register</button>
              </div>
              <input
                value={authUsername}
                onChange={(event) => setAuthUsername(event.target.value)}
                placeholder="username"
              />
              <input
                type="password"
                value={authPassword}
                onChange={(event) => setAuthPassword(event.target.value)}
                placeholder="password"
              />
              <button type="submit" disabled={authLoading}>
                {authLoading ? "Please wait..." : authMode === "register" ? "Create account" : "Login"}
              </button>
            </form>
          )}
        </div>

        <form className="search" onSubmit={handleSearch}>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Try: Interstellar, Hindi movies, Telugu series"
          />
          <button type="submit" disabled={loading}>{loading ? "Searching..." : "Recommend"}</button>
        </form>

        {suggestions.length > 0 && (
          <div className="suggestions">
            {suggestions.map((item) => (
              <button key={item} onClick={() => setQuery(item)}>{item}</button>
            ))}
          </div>
        )}

        {error && <div className="error">{error}</div>}
      </header>

      {recommendations.length > 0 && (
        <section>
          <h2>Results</h2>
          <div className="grid">
            {recommendations.map((movie) => (
              <PosterCard key={`${movie.title}-${movie.year || "na"}`} movie={movie} onToggleWatch={toggleWatch} watchedSet={watchedSet} />
            ))}
          </div>
        </section>
      )}

      <section>
        <h2>For You</h2>
        {!token && <p className="empty">Login to unlock your personal recommendations.</p>}
        {token && personalized.length === 0 && <p className="empty">Watch a few titles to unlock personalized rows.</p>}
        {personalized.map((section) => (
          <div key={section.title} className="section-block">
            <h3>{section.title}</h3>
            <p>{section.reason}</p>
            <div className="row-scroll">
              {section.movies.map((movie) => (
                <PosterCard key={`${section.title}-${movie.title}`} movie={movie} onToggleWatch={toggleWatch} watchedSet={watchedSet} />
              ))}
            </div>
          </div>
        ))}
      </section>

      <section>
        <h2>Popular Right Now</h2>
        <div className="grid">
          {popular.map((movie) => (
            <PosterCard key={`popular-${movie.title}`} movie={movie} onToggleWatch={toggleWatch} watchedSet={watchedSet} />
          ))}
        </div>
      </section>
    </div>
  );
}
