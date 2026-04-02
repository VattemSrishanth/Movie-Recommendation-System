import { getUserById, verifyToken } from "./authService.js";

function extractToken(req) {
  const authHeader = req.headers.authorization;
  if (!authHeader || typeof authHeader !== "string") {
    return null;
  }

  const [scheme, token] = authHeader.split(" ");
  if (!scheme || !token || scheme.toLowerCase() !== "bearer") {
    return null;
  }
  return token;
}

export function requireAuth(req, res, next) {
  try {
    const token = extractToken(req);
    if (!token) {
      res.status(401).json({ error: "Authentication required" });
      return;
    }

    const payload = verifyToken(token);
    const user = getUserById(payload.sub);
    if (!user) {
      res.status(401).json({ error: "Invalid token" });
      return;
    }

    req.user = user;
    next();
  } catch {
    res.status(401).json({ error: "Invalid or expired token" });
  }
}

export function optionalAuth(req, _res, next) {
  try {
    const token = extractToken(req);
    if (!token) {
      next();
      return;
    }

    const payload = verifyToken(token);
    const user = getUserById(payload.sub);
    if (user) {
      req.user = user;
    }
    next();
  } catch {
    next();
  }
}
