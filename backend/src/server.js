import cors from "cors";
import express from "express";
import rateLimit from "express-rate-limit";

import { cache } from "./cacheService.js";
import { issueToken, registerUser, verifyUser } from "./authService.js";
import { optionalAuth, requireAuth } from "./authMiddleware.js";
import { runPythonBridge } from "./pythonService.js";
import {
  addToWatchHistory,
  loadWatchHistory,
  removeFromWatchHistory,
} from "./watchHistory.js";

const app = express();
const PORT = Number(process.env.PORT || 4000);

const CACHE_TTL = {
  popular: 1000 * 60 * 5,
  autocomplete: 1000 * 60 * 10,
  recommend: 1000 * 60 * 2,
  personalized: 1000 * 45,
  watched: 1000 * 30,
};

const apiLimiter = rateLimit({
  windowMs: Number(process.env.RATE_LIMIT_WINDOW_MS || 15 * 60 * 1000),
  max: Number(process.env.RATE_LIMIT_MAX || 300),
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: "Too many requests. Please try again later." },
});

const authLimiter = rateLimit({
  windowMs: Number(process.env.AUTH_RATE_LIMIT_WINDOW_MS || 15 * 60 * 1000),
  max: Number(process.env.AUTH_RATE_LIMIT_MAX || 30),
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: "Too many auth attempts. Please try again later." },
});

app.use(cors());
app.use(express.json());
app.use("/api", apiLimiter);
app.use("/api/auth", authLimiter);

function clampNumber(value, fallback, min, max) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  return Math.min(max, Math.max(min, Math.floor(parsed)));
}

async function getCachedOrCompute(key, ttlMs, producer) {
  const cached = cache.get(key);
  if (cached !== undefined) {
    return cached;
  }
  const value = await producer();
  cache.set(key, value, ttlMs);
  return value;
}

function invalidateUserRecommendationCache(userId) {
  cache.deleteByPrefix(`personalized:${userId}:`);
  cache.deleteByPrefix(`watched:${userId}:`);
}

app.post("/api/auth/register", async (req, res) => {
  try {
    const user = await registerUser(req.body?.username, req.body?.password);
    const token = issueToken(user);
    res.status(201).json({ token, user });
  } catch (error) {
    res.status(400).json({ error: error.message });
  }
});

app.post("/api/auth/login", async (req, res) => {
  try {
    const user = await verifyUser(req.body?.username, req.body?.password);
    const token = issueToken(user);
    res.json({ token, user });
  } catch (error) {
    res.status(401).json({ error: error.message });
  }
});

app.get("/api/auth/me", requireAuth, (req, res) => {
  res.json({ user: req.user });
});

app.get("/api/health", (_req, res) => {
  res.json({ status: "ok" });
});

app.get("/api/popular", async (req, res) => {
  try {
    const count = clampNumber(req.query.count, 18, 1, 50);
    const cacheKey = `popular:${count}`;
    const data = await getCachedOrCompute(cacheKey, CACHE_TTL.popular, () =>
      runPythonBridge("popular", ["--count", String(count)])
    );
    res.json(data);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.get("/api/personalized", requireAuth, async (req, res) => {
  try {
    const perSection = clampNumber(req.query.perSection, 12, 1, 30);
    const watchHistory = loadWatchHistory(req.user.id);
    const cacheKey = `personalized:${req.user.id}:${perSection}`;
    const data = await getCachedOrCompute(cacheKey, CACHE_TTL.personalized, () =>
      runPythonBridge("personalized", [
        "--per-section",
        String(perSection),
        "--titles-json",
        JSON.stringify(watchHistory),
      ])
    );
    res.json({ watched_count: watchHistory.length, ...data });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.post("/api/recommend", optionalAuth, async (req, res) => {
  try {
    const movieName = String(req.body?.movie_name || "").trim();
    if (!movieName) {
      res.status(400).json({ error: "movie_name is required" });
      return;
    }
    const topN = clampNumber(req.body?.top_n, 18, 1, 50);
    const userPart = req.user ? `user:${req.user.id}` : "anon";
    const cacheKey = `recommend:${userPart}:${movieName.toLowerCase()}:${topN}`;
    const data = await getCachedOrCompute(cacheKey, CACHE_TTL.recommend, () =>
      runPythonBridge("recommend", [
        "--query",
        movieName,
        "--top-n",
        String(topN),
      ])
    );
    res.json(data);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.get("/api/autocomplete", async (req, res) => {
  try {
    const query = String(req.query.q || "").trim();
    if (!query) {
      res.json({ suggestions: [] });
      return;
    }
    const limit = clampNumber(req.query.limit, 12, 1, 20);
    const cacheKey = `autocomplete:${query.toLowerCase()}:${limit}`;
    const data = await getCachedOrCompute(cacheKey, CACHE_TTL.autocomplete, () =>
      runPythonBridge("autocomplete", ["--query", query, "--limit", String(limit)])
    );
    res.json(data);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.get("/api/watched", requireAuth, async (req, res) => {
  try {
    const watchHistory = loadWatchHistory(req.user.id);
    const cacheKey = `watched:${req.user.id}`;
    const data = await getCachedOrCompute(cacheKey, CACHE_TTL.watched, () =>
      runPythonBridge("watched", ["--titles-json", JSON.stringify(watchHistory)])
    );
    res.json({ watched_count: watchHistory.length, ...data });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.post("/api/watch", requireAuth, (req, res) => {
  const result = addToWatchHistory(req.user.id, req.body?.title);
  if (result.error) {
    res.status(400).json(result);
    return;
  }
  invalidateUserRecommendationCache(req.user.id);
  res.json(result);
});

app.post("/api/unwatch", requireAuth, (req, res) => {
  const result = removeFromWatchHistory(req.user.id, req.body?.title);
  if (result.error) {
    res.status(400).json(result);
    return;
  }
  invalidateUserRecommendationCache(req.user.id);
  res.json(result);
});

app.listen(PORT, () => {
  console.log(`Movie API listening on http://localhost:${PORT}`);
});
