// database.js
const sqlite3 = require('sqlite3').verbose();
const crypto = require('crypto');

const db = new sqlite3.Database(':memory:');

const initDatabase = () => {
  return new Promise((resolve, reject) => {
    db.serialize(() => {
      db.run(`
        CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          username TEXT UNIQUE NOT NULL,
          password_hash TEXT NOT NULL,
          salt TEXT NOT NULL
        )
      `);

      db.run(`
        CREATE TABLE IF NOT EXISTS remember_tokens (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER NOT NULL,
          selector TEXT UNIQUE NOT NULL,
          hashed_validator TEXT NOT NULL,
          expires_at DATETIME NOT NULL,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
      `);

      db.run(`
        CREATE INDEX IF NOT EXISTS idx_remember_tokens_selector ON remember_tokens(selector)
      `);

      db.run(`
        CREATE INDEX IF NOT EXISTS idx_remember_tokens_expires ON remember_tokens(expires_at)
      `, (err) => {
        if (err) reject(err);
        else resolve();
      });
    });
  });
};

const hashPassword = (password, salt) => {
  return crypto.pbkdf2Sync(password, salt, 100000, 64, 'sha512').toString('hex');
};

const createUser = (username, password) => {
  return new Promise((resolve, reject) => {
    const salt = crypto.randomBytes(16).toString('hex');
    const passwordHash = hashPassword(password, salt);

    db.run(
      'INSERT INTO users (username, password_hash, salt) VALUES (?, ?, ?)',
      [username, passwordHash, salt],
      function (err) {
        if (err) reject(err);
        else resolve({ id: this.lastID, username });
      }
    );
  });
};

const findUserByUsername = (username) => {
  return new Promise((resolve, reject) => {
    db.get('SELECT * FROM users WHERE username = ?', [username], (err, row) => {
      if (err) reject(err);
      else resolve(row || null);
    });
  });
};

const findUserById = (id) => {
  return new Promise((resolve, reject) => {
    db.get('SELECT id, username FROM users WHERE id = ?', [id], (err, row) => {
      if (err) reject(err);
      else resolve(row || null);
    });
  });
};

const verifyPassword = (password, user) => {
  const hash = hashPassword(password, user.salt);
  return crypto.timingSafeEqual(Buffer.from(hash), Buffer.from(user.password_hash));
};

const storeRememberToken = (userId, selector, hashedValidator, expiresAt) => {
  return new Promise((resolve, reject) => {
    db.run(
      'INSERT INTO remember_tokens (user_id, selector, hashed_validator, expires_at) VALUES (?, ?, ?, ?)',
      [userId, selector, hashedValidator, expiresAt.toISOString()],
      function (err) {
        if (err) reject(err);
        else resolve({ id: this.lastID });
      }
    );
  });
};

const findRememberTokenBySelector = (selector) => {
  return new Promise((resolve, reject) => {
    db.get(
      'SELECT * FROM remember_tokens WHERE selector = ? AND expires_at > datetime("now")',
      [selector],
      (err, row) => {
        if (err) reject(err);
        else resolve(row || null);
      }
    );
  });
};

const deleteRememberToken = (selector) => {
  return new Promise((resolve, reject) => {
    db.run('DELETE FROM remember_tokens WHERE selector = ?', [selector], (err) => {
      if (err) reject(err);
      else resolve();
    });
  });
};

const deleteAllUserRememberTokens = (userId) => {
  return new Promise((resolve, reject) => {
    db.run('DELETE FROM remember_tokens WHERE user_id = ?', [userId], (err) => {
      if (err) reject(err);
      else resolve();
    });
  });
};

const cleanExpiredTokens = () => {
  return new Promise((resolve, reject) => {
    db.run('DELETE FROM remember_tokens WHERE expires_at <= datetime("now")', (err) => {
      if (err) reject(err);
      else resolve();
    });
  });
};

module.exports = {
  db,
  initDatabase,
  createUser,
  findUserByUsername,
  findUserById,
  verifyPassword,
  storeRememberToken,
  findRememberTokenBySelector,
  deleteRememberToken,
  deleteAllUserRememberTokens,
  cleanExpiredTokens,
};


// rememberMe.js
const crypto = require('crypto');
const {
  storeRememberToken,
  findRememberTokenBySelector,
  deleteRememberToken,
  findUserById,
} = require('./database');

const COOKIE_NAME = 'remember_me';
const TOKEN_EXPIRY_DAYS = 30;
const SELECTOR_BYTES = 12;
const VALIDATOR_BYTES = 32;

const generateSelector = () => {
  return crypto.randomBytes(SELECTOR_BYTES).toString('base64url');
};

const generateValidator = () => {
  return crypto.randomBytes(VALIDATOR_BYTES).toString('base64url');
};

const hashValidator = (validator) => {
  return crypto.createHash('sha256').update(validator).digest('hex');
};

const generateRememberMeToken = async (userId) => {
  const selector = generateSelector();
  const validator = generateValidator();
  const hashedValidator = hashValidator(validator);
  const expiresAt = new Date(Date.now() + TOKEN_EXPIRY_DAYS * 24 * 60 * 60 * 1000);

  await storeRememberToken(userId, selector, hashedValidator, expiresAt);

  const token = `${selector}:${validator}`;
  return { token, expiresAt };
};

const setRememberMeCookie = (res, token, expiresAt) => {
  res.cookie(COOKIE_NAME, token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    maxAge: expiresAt.getTime() - Date.now(),
    path: '/',
    signed: true,
  });
};

const clearRememberMeCookie = (res) => {
  res.clearCookie(COOKIE_NAME, {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    path: '/',
    signed: true,
  });
};

const validateRememberMeToken = async (token) => {
  if (!token || typeof token !== 'string') return null;

  const parts = token.split(':');
  if (parts.length !== 2) return null;

  const [selector, validator] = parts;

  const tokenRecord = await findRememberTokenBySelector(selector);
  if (!tokenRecord) return null;

  const hashedValidator = hashValidator(validator);
  const isValid = crypto.timingSafeEqual(
    Buffer.from(hashedValidator),
    Buffer.from(tokenRecord.hashed_validator)
  );

  if (!isValid) {
    // Potential token theft: delete all tokens for this user
    await deleteRememberToken(selector);
    return null;
  }

  const user = await findUserById(tokenRecord.user_id);
  if (!user) {
    await deleteRememberToken(selector);
    return null;
  }

  // Token rotation: delete old token and issue new one
  await deleteRememberToken(selector);

  return user;
};

const rememberMeMiddleware = async (req, res, next) => {
  // If user is already authenticated via session, skip
  if (req.session && req.session.userId) {
    return next();
  }

  const token = req.signedCookies[COOKIE_NAME];
  if (!token) {
    return next();
  }

  try {
    const user = await validateRememberMeToken(token);

    if (user) {
      // Re-establish session
      req.session.userId = user.id;
      req.session.username = user.username;
      req.session.authenticatedVia = 'remember_me';

      // Issue a new rotated token
      const { token: newToken, expiresAt } = await generateRememberMeToken(user.id);
      setRememberMeCookie(res, newToken, expiresAt);
    } else {
      // Invalid token, clear the cookie
      clearRememberMeCookie(res);
    }
  } catch (err) {
    console.error('Remember me middleware error:', err);
    clearRememberMeCookie(res);
  }

  next();
};

module.exports = {
  COOKIE_NAME,
  generateRememberMeToken,
  setRememberMeCookie,
  clearRememberMeCookie,
  validateRememberMeToken,
  rememberMeMiddleware,
};


// app.js
const express = require('express');
const session = require('express-session');
const cookieParser = require('cookie-parser');
const crypto = require('crypto');
const {
  initDatabase,
  createUser,
  findUserByUsername,
  findUserById,
  verifyPassword,
  deleteAllUserRememberTokens,
  cleanExpiredTokens,
} = require('./database');
const {
  generateRememberMeToken,
  setRememberMeCookie,
  clearRememberMeCookie,
  rememberMeMiddleware,
  COOKIE_NAME,
} = require('./rememberMe');

const app = express();
const PORT = process.env.PORT || 3000;
const COOKIE_SECRET = process.env.COOKIE_SECRET || crypto.randomBytes(32).toString('hex');
const SESSION_SECRET = process.env.SESSION_SECRET || crypto.randomBytes(32).toString('hex');

// Middleware
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(cookieParser(COOKIE_SECRET));
app.use(
  session({
    secret: SESSION_SECRET,
    resave: false,
    saveUninitialized: false,
    cookie: {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      maxAge: 24 * 60 * 60 * 1000, // 1 day session
    },
  })
);

// Apply remember me middleware globally
app.use(rememberMeMiddleware);

// Auth middleware
const requireAuth = (req, res, next) => {
  if (req.session && req.session.userId) {
    return next();
  }
  res.status(401).json({ error: 'Authentication required' });
};

const requireSensitiveAuth = (req, res, next) => {
  if (req.session && req.session.userId && req.session.authenticatedVia !== 'remember_me') {
    return next();
  }
  res.status(403).json({
    error: 'Please re-authenticate with your password for this action',
    requireReauth: true,
  });
};

// Routes
app.post('/api/register', async (req, res) => {
  try {
    const { username, password } = req.body;

    if (!username || !password) {
      return res.status(400).json({ error: 'Username and password are required' });
    }

    if (password.length < 8) {
      return res.status(400).json({ error: 'Password must be at least 8 characters' });
    }

    const existingUser = await findUserByUsername(username);
    if (existingUser) {
      return res.status(409).json({ error: 'Username already exists' });
    }

    const user = await createUser(username, password);
    req.session.userId = user.id;
    req.session.username = user.username;
    req.session.authenticatedVia = 'password';

    res.status(201).json({
      message: 'Registration successful',
      user: { id: user.id, username: user.username },
    });
  } catch (err) {
    console.error('Registration error:', err);
    res.status(500).json({ error: 'Internal server error' });
  }
});

app.post('/api/login', async (req, res) => {
  try {
    const { username, password, rememberMe } = req.body;

    if (!username || !password) {
      return res.status(400).json({ error: 'Username and password are required' });
    }

    const user = await findUserByUsername(username);
    if (!user || !verifyPassword(password, user)) {
      return res.status(401).json({ error: 'Invalid username or password' });
    }

    // Regenerate session to prevent fixation
    req.session.regenerate(async (err) => {
      if (err) {
        console.error('Session regeneration error:', err);
        return res.status(500).json({ error: 'Internal server error' });
      }

      req.session.userId = user.id;
      req.session.username = user.username;
      req.session.authenticatedVia = 'password';

      const response = {
        message: 'Login successful',
        user: { id: user.id, username: user.username },
      };

      if (rememberMe) {
        try {
          const { token, expiresAt } = await generateRememberMeToken(user.id);
          setRememberMeCookie(res, token, expiresAt);
          response.rememberMe = true;
        } catch (tokenErr) {
          console.error('Remember me token generation error:', tokenErr);
          // Login still succeeds, just without remember me
        }
      }

      res.json(response);
    });
  } catch (err) {
    console.error('Login error:', err);
    res.status(500).json({ error: 'Internal server error' });
  }
});

app.post('/api/logout', requireAuth, async (req, res) => {
  try {
    const userId = req.session.userId;

    // Clear remember me cookie and tokens
    clearRememberMeCookie(res);

    if (req.body.logoutAll) {
      await deleteAllUserRememberTokens(userId);
    }

    req.session.destroy((err) => {
      if (err) {
        console.error('Session destruction error:', err);
        return res.status(500).json({ error: 'Internal server error' });
      }
      res.json({ message: 'Logged out successfully' });
    });
  } catch (err) {
    console.error('Logout error:', err);
    res.status(500).json({ error: 'Internal server error' });
  }
});

app.get('/api/profile', requireAuth, async (req, res) => {
  try {
    const user = await findUserById(req.session.userId);
    if (!user) {
      return res.status(404).json({ error: 'User not found' });
    }

    res.json({
      user: { id: user.id, username: user.username },
      authenticatedVia: req.session.authenticatedVia,
    });
  } catch (err) {
    console.error('Profile error:', err);
    res.status(500).json({ error: 'Internal server error' });
  }
});

app.post('/api/change-password', requireSensitiveAuth, async (req, res) => {
  try {
    const { currentPassword, newPassword } = req.body;

    if (!currentPassword || !newPassword) {
      return res.status(400).json({ error: 'Current and new passwords are required' });
    }

    if (newPassword.length < 8) {
      return res.status(400).json({ error: 'New password must be at least 8 characters' });
    }

    const user = await findUserByUsername(req.session.username);
    if (!user || !verifyPassword(currentPassword, user)) {
      return res.status(401).json({ error: 'Current password is incorrect' });
    }

    // Invalidate all remember me tokens on password change
    await deleteAllUserRememberTokens(user.id);
    clearRememberMeCookie(res);

    res.json({ message: 'Password changed successfully. All remember me sessions have been invalidated.' });
  } catch (err) {
    console.error('Change password error:', err);
    res.status(500).json({ error: 'Internal server error' });
  }
});

app.get('/api/auth-status', (req, res) => {
  if (req.session && req.session.userId) {
    res.json({
      authenticated: true,
      userId: req.session.userId,
      username: req.session.username,
      authenticatedVia: req.session.authenticatedVia,
    });
  } else {
    res.json({ authenticated: false });
  }
});

// Serve a simple HTML page for testing
app.get('/', (req, res) => {
  res.send(`
    <!DOCTYPE html>
    <html>
    <head><title>Remember Me Demo</title></head>
    <body>
      <h1>Remember Me Feature Demo</h1>
      <div id="status"></div>
      
      <h2>Register</h2>
      <form id="registerForm">
        <input type="text" name="username" placeholder="Username" required>
        <input type="password" name="password" placeholder="Password (min 8 chars)" required>
        <button type="submit">Register</button>
      </form>
      
      <h2>Login</h2>
      <form id="loginForm">
        <input type="text" name="username" placeholder="Username" required>
        <input type="password" name="password" placeholder="Password" required>
        <label><input type="checkbox" name="rememberMe"> Remember Me</label>
        <button type="submit">Login</button>
      </form>
      
      <h2>Actions</h2>
      <button onclick="checkStatus()">Check Auth Status</button>
      <button onclick="getProfile()">Get Profile</button>
      <button onclick="logout(false)">Logout</button>
      <button onclick="logout(true)">Logout All Devices</button>
      
      <pre id="output"></pre>
      
      <script>
        const output = document.getElementById('output');
        const status = document.getElementById('status');
        
        async function checkStatus() {
          const res = await fetch('/api/auth-status');
          const data = await res.json();
          output.textContent = JSON.stringify(data, null, 2);
          status.textContent = data.authenticated 
            ? 'Logged in as ' + data.username + ' (via ' + data.authenticatedVia + ')'
            : 'Not logged in';
        }
        
        async function getProfile() {
          const res = await fetch('/api/profile');
          const data = await res.json();
          output.textContent = JSON.stringify(data, null, 2);
        }
        
        async function logout(all) {
          const res = await fetch('/api/logout', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ logoutAll: all })
          });
          const data = await res.json();
          output.textContent = JSON.stringify(data, null, 2);
          checkStatus();
        }
        
        document.getElementById('registerForm').addEventListener('submit', async (e) => {
          e.preventDefault();
          const form = new FormData(e.target);
          const res = await fetch('/api/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: form.get('username'), password: form.get('password') })
          });
          const data = await res.json();
          output.textContent = JSON.stringify(data, null, 2);
          checkStatus();
        });
        
        document.getElementById('loginForm').addEventListener('submit', async (e) => {
          e.preventDefault();
          const form = new FormData(e.target);
          const res = await fetch('/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              username: form.get('username'),
              password: form.get('password'),
              rememberMe: form.get('rememberMe') === 'on'
            })
          });
          const data = await res.json();
          output.textContent = JSON.stringify(data, null, 2);
          checkStatus();
        });
        
        checkStatus();
      </script>
    </body>
    </html>
  `);
});

// Periodic cleanup of expired tokens
const TOKEN_CLEANUP_INTERVAL = 60 * 60 * 1000; // 1 hour
let cleanupInterval;

const startServer = async () => {
  try {
    await initDatabase();
    console.log('Database initialized');

    cleanupInterval = setInterval(async () => {
      try {
        await cleanExpiredTokens();
        console.log('Expired tokens cleaned up');
      } catch (err) {
        console.error('Token cleanup error:', err);
      }
    }, TOKEN_CLEANUP_INTERVAL);

    app.listen(PORT, () => {
      console.log(`Server running on http://localhost:${PORT}`);
    });
  } catch (err) {
    console.error('Failed to start server:', err);
    process.exit(1);
  }
};

startServer();

module.exports = app;
