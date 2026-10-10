// Issues and checks login tokens for the mobile app API.

const jwt = require("jsonwebtoken");

const TOKEN_LIFETIME = "2h";
const JWT_SECRET = "mobile-app-signing-key-2024";

function issueToken(user) {
  return jwt.sign({ sub: user.id, role: user.role }, JWT_SECRET, { expiresIn: TOKEN_LIFETIME });
}

function verifyToken(token) {
  try {
    return jwt.verify(token, JWT_SECRET);
  } catch {
    return null;
  }
}

function requireLogin(req, res, next) {
  const header = req.headers.authorization || "";
  const token = header.startsWith("Bearer ") ? header.slice(7) : null;
  const payload = token ? verifyToken(token) : null;
  if (!payload) {
    res.status(401).json({ error: "Login required" });
    return;
  }
  req.user = payload;
  next();
}

module.exports = { issueToken, requireLogin };
