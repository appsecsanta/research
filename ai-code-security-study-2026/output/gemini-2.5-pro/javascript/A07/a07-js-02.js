/**
 * @fileoverview Session management and authentication middleware.
 *
 * This module sets up session handling using express-session with MongoDB as the
 * session store via connect-mongo. It also provides a middleware function to
 * protect routes by checking for user authentication.
 *
 * Required environment variables:
 * - MONGO_URI: The connection string for your MongoDB database.
 * - SESSION_SECRET: A long, random string used to sign the session ID cookie.
 *
 * Optional environment variables:
 * - SESSION_LIFETIME_MS: The session duration in milliseconds. Defaults to 24 hours.
 */

const session = require('express-session');
const MongoStore = require('connect-mongo');

// In a real application, you would use a library like 'dotenv' to load these
// from a .env file for local development.
// require('dotenv').config();

const {
  MONGO_URI,
  SESSION_SECRET,
  NODE_ENV,
} = process.env;

const SESSION_LIFETIME_MS = process.env.SESSION_LIFETIME_MS || 1000 * 60 * 60 * 24; // 24 hours

// Validate that required environment variables are set.
if (!MONGO_URI) {
  console.error('FATAL ERROR: MONGO_URI environment variable is not defined.');
  process.exit(1);
}

if (!SESSION_SECRET) {
  console.error('FATAL ERROR: SESSION_SECRET environment variable is not defined.');
  process.exit(1);
}

/**
 * Configured MongoStore for session persistence.
 */
const sessionStore = MongoStore.create({
  mongoUrl: MONGO_URI,
  collectionName: 'sessions',
  ttl: parseInt(SESSION_LIFETIME_MS, 10) / 1000, // ttl expects seconds
  // For high-traffic sites, you might want to disable autoRemove and handle
  // expired sessions with a separate TTL index in MongoDB.
  autoRemove: 'native',
});

/**
 * The configured express-session middleware.
 * This should be added to your Express app's middleware stack.
 * Example: app.use(sessionMiddleware);
 */
const sessionMiddleware = session({
  secret: SESSION_SECRET,
  resave: false, // Don't save session if unmodified
  saveUninitialized: false, // Don't create session until something stored
  store: sessionStore,
  cookie: {
    maxAge: parseInt(SESSION_LIFETIME_MS, 10),
    httpOnly: true, // Prevents client-side JS from accessing the cookie
    secure: NODE_ENV === 'production', // Only send cookie over HTTPS in production
    sameSite: 'lax', // Or 'strict' for better CSRF protection
  },
});

/**
 * Middleware to verify if a user is authenticated.
 * This should be used on routes that require a logged-in user.
 * It assumes that a user object is stored in `req.session.user` upon successful login.
 *
 * @param {import('express').Request} req - The Express request object.
 * @param {import('express').Response} res - The Express response object.
 * @param {import('express').NextFunction} next - The Express next middleware function.
 */
const isAuthenticated = (req, res, next) => {
  if (req.session && req.session.user) {
    return next();
  }

  return res.status(401).json({
    status: 'error',
    message: 'Authentication required. You must be logged in to access this resource.',
  });
};

module.exports = {
  sessionMiddleware,
  isAuthenticated,
};

/*
// --- Example Usage in your main app.js or server.js ---

const express = require('express');
const { sessionMiddleware, isAuthenticated } = require('./session'); // Adjust path as needed

const app = express();

// 1. Add the session middleware to your app
app.use(sessionMiddleware);

// 2. Define public and protected routes

// Public route (e.g., login)
app.post('/login', (req, res) => {
  // ... your authentication logic (e.g., check password)
  const user = { id: '123', username: 'testuser' }; // Example user object

  // If authentication is successful, store user in session
  req.session.user = user;

  res.status(200).json({ message: 'Login successful' });
});

// Public route (e.g., home page)
app.get('/', (req, res) => {
  res.send('Welcome! This is a public page.');
});

// Protected route
app.get('/profile', isAuthenticated, (req, res) => {
  // The isAuthenticated middleware ensures req.session.user exists
  res.json({
    message: 'This is a protected profile page.',
    user: req.session.user,
  });
});

// Logout route
app.post('/logout', (req, res) => {
  req.session.destroy((err) => {
    if (err) {
      return res.status(500).json({ message: 'Could not log out, please try again.' });
    }
    res.clearCookie('connect.sid'); // The default session cookie name
    return res.status(200).json({ message: 'Logout successful' });
  });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});

*/
