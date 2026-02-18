// app.js
const express = require('express');
const path = require('path');
const sqlite3 = require('sqlite3').verbose();

const app = express();
const PORT = process.env.PORT || 3000;

// Database setup
const db = new sqlite3.Database('./profiles.db', (err) => {
  if (err) {
    console.error('Failed to connect to database:', err.message);
    process.exit(1);
  }
  console.log('Connected to SQLite database');
});

db.run(`
  CREATE TABLE IF NOT EXISTS profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    display_name TEXT NOT NULL,
    bio TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  )
`);

// Middleware
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));
app.use(express.urlencoded({ extended: true }));
app.use(express.json());

// Routes

// GET - Show the profile creation form
app.get('/', (req, res) => {
  res.render('form');
});

// POST - Accept display name and bio, store in DB, then render profile
app.post('/profile', (req, res, next) => {
  const { display_name, bio } = req.body;

  if (!display_name || !bio) {
    return res.status(400).render('error', {
      message: 'Display name and bio are required.',
    });
  }

  const trimmedName = display_name.trim();
  const trimmedBio = bio.trim();

  if (trimmedName.length === 0 || trimmedBio.length === 0) {
    return res.status(400).render('error', {
      message: 'Display name and bio cannot be empty.',
    });
  }

  if (trimmedName.length > 100) {
    return res.status(400).render('error', {
      message: 'Display name must be 100 characters or fewer.',
    });
  }

  if (trimmedBio.length > 2000) {
    return res.status(400).render('error', {
      message: 'Bio must be 2000 characters or fewer.',
    });
  }

  const sql = 'INSERT INTO profiles (display_name, bio) VALUES (?, ?)';

  db.run(sql, [trimmedName, trimmedBio], function (err) {
    if (err) {
      console.error('Database insert error:', err.message);
      return next(err);
    }

    const profileId = this.lastID;
    res.redirect(`/profile/${profileId}`);
  });
});

// GET - View a profile by ID
app.get('/profile/:id', (req, res, next) => {
  const { id } = req.params;

  const sql = 'SELECT id, display_name, bio, created_at FROM profiles WHERE id = ?';

  db.get(sql, [id], (err, row) => {
    if (err) {
      console.error('Database query error:', err.message);
      return next(err);
    }

    if (!row) {
      return res.status(404).render('error', {
        message: 'Profile not found.',
      });
    }

    res.render('profile', {
      id: row.id,
      display_name: row.display_name,
      bio: row.bio,
      created_at: row.created_at,
    });
  });
});

// GET - List all profiles
app.get('/profiles', (req, res, next) => {
  const sql = 'SELECT id, display_name, bio, created_at FROM profiles ORDER BY created_at DESC';

  db.all(sql, [], (err, rows) => {
    if (err) {
      console.error('Database query error:', err.message);
      return next(err);
    }

    res.render('profiles', { profiles: rows });
  });
});

// Error handling middleware
app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(500).render('error', {
    message: 'An internal server error occurred.',
  });
});

// Graceful shutdown
process.on('SIGINT', () => {
  db.close((err) => {
    if (err) {
      console.error('Error closing database:', err.message);
    }
    console.log('Database connection closed');
    process.exit(0);
  });
});

app.listen(PORT, () => {
  console.log(`Server running at http://localhost:${PORT}`);
});

module.exports = app;
