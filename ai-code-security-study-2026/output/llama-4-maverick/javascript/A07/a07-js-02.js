const expressSession = require('express-session');
const MongoStore = require('connect-mongo');

const sessionConfig = {
  secret: process.env.SESSION_SECRET,
  resave: false,
  saveUninitialized: false,
  store: MongoStore.create({
    mongoUrl: process.env.MONGODB_URI,
    collectionName: 'sessions',
  }),
  cookie: {
    httpOnly: true,
    maxAge: 24 * 60 * 60 * 1000, // 1 day
  },
};

const sessionMiddleware = expressSession(sessionConfig);

const authenticate = (req, res, next) => {
  if (req.session && req.session.user) {
    next();
  } else {
    res.status(401).send('Unauthorized');
  }
};

module.exports = { sessionMiddleware, authenticate };
