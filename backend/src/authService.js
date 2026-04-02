import bcrypt from "bcryptjs";
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import jwt from "jsonwebtoken";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const backendRoot = path.resolve(__dirname, "..");
const dataDir = path.join(backendRoot, "data");
const usersFile = path.join(dataDir, "users.json");

const JWT_SECRET = process.env.JWT_SECRET || "dev_jwt_secret_change_me";
const JWT_EXPIRES_IN = process.env.JWT_EXPIRES_IN || "7d";

function ensureStore() {
  if (!fs.existsSync(dataDir)) {
    fs.mkdirSync(dataDir, { recursive: true });
  }
  if (!fs.existsSync(usersFile)) {
    fs.writeFileSync(usersFile, "[]", "utf8");
  }
}

function readUsers() {
  ensureStore();
  try {
    const raw = fs.readFileSync(usersFile, "utf8");
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed;
  } catch {
    return [];
  }
}

function writeUsers(users) {
  ensureStore();
  fs.writeFileSync(usersFile, JSON.stringify(users, null, 2), "utf8");
}

function normalizeUsername(username) {
  return String(username || "").trim().toLowerCase();
}

function toPublicUser(user) {
  return {
    id: user.id,
    username: user.username,
    created_at: user.created_at,
  };
}

export async function registerUser(usernameInput, passwordInput) {
  const username = normalizeUsername(usernameInput);
  const password = String(passwordInput || "");

  if (!username) {
    throw new Error("username is required");
  }
  if (username.length < 3) {
    throw new Error("username must be at least 3 characters");
  }
  if (password.length < 6) {
    throw new Error("password must be at least 6 characters");
  }

  const users = readUsers();
  const exists = users.some((user) => normalizeUsername(user.username) === username);
  if (exists) {
    throw new Error("username already exists");
  }

  const password_hash = await bcrypt.hash(password, 10);
  const user = {
    id: crypto.randomUUID(),
    username,
    password_hash,
    created_at: new Date().toISOString(),
  };

  users.push(user);
  writeUsers(users);
  return toPublicUser(user);
}

export async function verifyUser(usernameInput, passwordInput) {
  const username = normalizeUsername(usernameInput);
  const password = String(passwordInput || "");

  if (!username || !password) {
    throw new Error("username and password are required");
  }

  const users = readUsers();
  const user = users.find((item) => normalizeUsername(item.username) === username);
  if (!user) {
    throw new Error("Invalid credentials");
  }

  const ok = await bcrypt.compare(password, user.password_hash || "");
  if (!ok) {
    throw new Error("Invalid credentials");
  }

  return toPublicUser(user);
}

export function getUserById(userId) {
  if (!userId) {
    return null;
  }
  const users = readUsers();
  const user = users.find((item) => item.id === userId);
  return user ? toPublicUser(user) : null;
}

export function issueToken(user) {
  return jwt.sign(
    {
      sub: user.id,
      username: user.username,
    },
    JWT_SECRET,
    { expiresIn: JWT_EXPIRES_IN }
  );
}

export function verifyToken(token) {
  return jwt.verify(token, JWT_SECRET);
}
