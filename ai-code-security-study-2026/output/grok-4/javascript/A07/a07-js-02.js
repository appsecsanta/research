const session = require('express-session');
const MongoStore = require('connect-mongo');

// Session configuration
const sessionConfig = {
  secret: process.env.SESSION_SECRET || 'default-secret-key', // Use environment variable in production
  resave: false,
  saveUninitialized: false,
  store: MongoStore.create({
    mongoUrl: process.env.MONGO_URI || 'mongodb://localhost:27017/session-db', // Use environment variable in production
    ttl: 14 * 24 * 60 * 60, // 14 days
    autoRemove: 'native'
  }),
  cookie: {
    secure: process.env.NODE_ENV === 'production',
    httpOnly: true,
    sameSite: 'strict',
    maxAge: 1000 * 60 * 60 * 24 // 1 day
  }
};

// Session middleware
const sessionMiddleware = session(sessionConfig);

// Authentication check middleware
const isAuthenticated = (req, res, next) => {
  if (req.session && req.session.user) {
    return next();
  }
  return res.status(401).json({ error: 'Unauthorized' });
};

module.exports = { sessionMiddleware, isAuthenticated };
