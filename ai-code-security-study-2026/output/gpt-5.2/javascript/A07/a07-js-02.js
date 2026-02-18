'use strict';

const session = require('express-session');
const MongoStore = require('connect-mongo');

function createSessionMiddleware(options = {}) {
  const {
    mongoUrl,
    secret,
    name = 'sid',
    collectionName = 'sessions',
    ttlSeconds = 60 * 60 * 24 * 14, // 14 days
    resave = false,
    saveUninitialized = false,
    rolling = false,
    cookie = {},
  } = options;

  if (!mongoUrl) throw new Error('createSessionMiddleware: "mongoUrl" is required');
  if (!secret) throw new Error('createSessionMiddleware: "secret" is required');

  const isProd = process.env.NODE_ENV === 'production';

  const store = MongoStore.create({
    mongoUrl,
    collectionName,
    ttl: ttlSeconds,
    touchAfter: 24 * 3600, // reduce write frequency
  });

  return session({
    name,
    secret,
    store,
    resave,
    saveUninitialized,
    rolling,
    proxy: isProd, // requires app.set('trust proxy', 1) when behind a proxy
    cookie: {
      httpOnly: true,
      secure: isProd,
      sameSite: 'lax',
      maxAge: ttlSeconds * 1000,
      ...cookie,
    },
  });
}

function requireAuth(options = {}) {
  const {
    sessionKey = 'user',
    userIdKey = 'userId',
    onUnauthenticated,
  } = options;

  return function requireAuthMiddleware(req, res, next) {
    const sess = req.session;
    const authenticated =
      !!sess &&
      (Boolean(sess[userIdKey]) ||
        (sess[sessionKey] && (sess[sessionKey].id || sess[sessionKey]._id)));

    if (authenticated) return next();

    if (typeof onUnauthenticated === 'function') {
      return onUnauthenticated(req, res, next);
    }

    const accept = req.headers.accept || '';
    const wantsJson = req.xhr || accept.includes('application/json');

    if (wantsJson) {
      return res.status(401).json({ error: 'Unauthorized' });
    }

    return res.redirect(302, '/login');
  };
}

module.exports = {
  createSessionMiddleware,
  requireAuth,
};
