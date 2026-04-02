import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const backendRoot = path.resolve(__dirname, "..");
const dataDir = path.join(backendRoot, "data");
const watchFile = path.join(dataDir, "watch_history.json");

function ensureStore() {
  if (!fs.existsSync(dataDir)) {
    fs.mkdirSync(dataDir, { recursive: true });
  }
  if (!fs.existsSync(watchFile)) {
    fs.writeFileSync(watchFile, "{}", "utf8");
  }
}

function loadAllHistories() {
  ensureStore();
  try {
    const raw = fs.readFileSync(watchFile, "utf8");
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return {};
    }
    return parsed;
  } catch {
    return {};
  }
}

function saveAllHistories(histories) {
  ensureStore();
  fs.writeFileSync(watchFile, JSON.stringify(histories, null, 2), "utf8");
}

export function loadWatchHistory(userId) {
  if (!userId) {
    return [];
  }
  const histories = loadAllHistories();
  const userTitles = histories[userId];
  if (!Array.isArray(userTitles)) {
    return [];
  }
  return userTitles.filter((item) => typeof item === "string" && item.trim());
}

export function saveWatchHistory(userId, titles) {
  if (!userId) {
    return;
  }
  const histories = loadAllHistories();
  histories[userId] = titles;
  saveAllHistories(histories);
}

export function addToWatchHistory(userId, title) {
  if (!userId) {
    return { error: "User is required" };
  }

  const cleaned = String(title || "").trim();
  if (!cleaned) {
    return { error: "No title provided" };
  }

  const current = loadWatchHistory(userId);
  if (!current.includes(cleaned)) {
    current.push(cleaned);
    saveWatchHistory(userId, current);
  }

  return { status: "added", title: cleaned, count: current.length };
}

export function removeFromWatchHistory(userId, title) {
  if (!userId) {
    return { error: "User is required" };
  }

  const cleaned = String(title || "").trim();
  if (!cleaned) {
    return { error: "No title provided" };
  }

  const current = loadWatchHistory(userId);
  const updated = current.filter((item) => item !== cleaned);
  saveWatchHistory(userId, updated);

  return { status: "removed", title: cleaned, count: updated.length };
}
