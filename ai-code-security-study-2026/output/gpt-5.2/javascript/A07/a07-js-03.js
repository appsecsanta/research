// file: auth/rememberMe.js
const crypto = require("crypto");
const RememberToken = require("../models/RememberToken");
const User = require("../models/User");

const COOKIE_NAME = "remember_me";
const REMEMBER_ME_DAYS = 30;

function now() {
  return new Date();
}

function addDays(date, days) {
  const d = new Date(date);
  d.setDate(d.getDate() + days);
  return d;
}

function sha256Hex(input) {
  return crypto.createHash("sha256").update(input).digest("hex");
}

function randomBase64Url(bytes) {
  return crypto.randomBytes(bytes).toString("base64url");
}

function safeEqualHex(aHex, bHex) {
  if (typeof aHex !== "string" || typeof bHex !== "string") return false;
  if (aHex.length !== bHex.length) return false;
  const a = Buffer.from(aHex, "hex");
  const b = Buffer.from(bHex, "hex");
  if (a.length !== b.length) return false;
  return crypto.timingSafeEqual(a, b);
}

function cookieOptions(req, maxAgeMs) {
  const isProd = req.app.get("env") === "production";
  return {
    httpOnly: true,
    secure: isProd,
    sameSite: "lax",
    path: "/",
    maxAge: maxAgeMs,
  };
}

function parseCookieValue(value) {
  if (!value || typeof value !== "string") return null;
  const parts = value.split(".");
  if (parts.length !== 2) return null;
  const [selector, validator] = parts;
  if (!selector || !validator) return null;
  if (selector.length < 8 || validator.length < 16) return null;
  return { selector, validator };
}

async function issueRememberMeToken(req, res, userId, { rotateExisting = false } = {}) {
  const selector = randomBase64Url(9);
  const validator = randomBase64Url(32);
  const validatorHash = sha256Hex(validator);

  const expiresAt = addDays(now(), REMEMBER_ME_DAYS);

  if (rotateExisting) {
    await RememberToken.deleteMany({ userId });
  }

  await RememberToken.create({
    userId,
    selector,
    validatorHash,
    expiresAt,
    lastUsedAt: null,
  });

  const value = `${selector}.${validator}`;
  const maxAgeMs = REMEMBER_ME_DAYS * 24 * 60 * 60 * 1000;

  res.cookie(COOKIE_NAME, value, cookieOptions(req, maxAgeMs));
}

async function clearRememberMe(req, res, { selector } = {}) {
  try {
    if (!selector) {
      const parsed = parseCookieValue(req.cookies?.[COOKIE_NAME]);
      selector = parsed?.selector;
    }
    if (selector) {
      await RememberToken.deleteOne({ selector });
    }
  } finally {
    res.clearCookie(COOKIE_NAME, cookieOptions(req, 0));
  }
}

async function rememberMeMiddleware(req, res, next) {
  try {
    if (req.session?.userId) return next();

    const raw = req.cookies?.[COOKIE_NAME];
    const parsed = parseCookieValue(raw);
    if (!parsed) return next();

    const { selector, validator } = parsed;

    const tokenDoc = await RememberToken.findOne({ selector }).lean();
    if (!tokenDoc) {
      res.clearCookie(COOKIE_NAME, cookieOptions(req, 0));
      return next();
    }

    if (new Date(tokenDoc.expiresAt).getTime() <= Date.now()) {
      await RememberToken.deleteOne({ selector });
      res.clearCookie(COOKIE_NAME, cookieOptions(req, 0));
      return next();
    }

    const presentedHash = sha256Hex(validator);
    if (!safeEqualHex(tokenDoc.validatorHash, presentedHash)) {
      // Possible theft attempt: invalidate this token
      await RememberToken.deleteOne({ selector });
      res.clearCookie(COOKIE_NAME, cookieOptions(req, 0));
      return next();
    }

    const user = await User.findById(tokenDoc.userId).lean();
    if (!user) {
      await RememberToken.deleteOne({ selector });
      res.clearCookie(COOKIE_NAME, cookieOptions(req, 0));
      return next();
    }

    // Establish session
    if (req.session) {
      req.session.userId = String(user._id);
    }
    req.user = user;

    // Rotate validator on every successful use
    const newValidator = randomBase64Url(32);
    const newHash = sha256Hex(newValidator);
    const newExpiresAt = addDays(now(), REMEMBER_ME_DAYS);

    await RememberToken.updateOne(
      { selector },
      { $set: { validatorHash: newHash, expiresAt: newExpiresAt, lastUsedAt: now() } }
    );

    const maxAgeMs = REMEMBER_ME_DAYS * 24 * 60 * 60 * 1000;
    res.cookie(COOKIE_NAME, `${selector}.${newValidator}`, cookieOptions(req, maxAgeMs));

    return next();
  } catch (err) {
    return next(err);
  }
}

module.exports = {
  COOKIE_NAME,
  REMEMBER_ME_DAYS,
  rememberMeMiddleware,
  issueRememberMeToken,
  clearRememberMe,
};
