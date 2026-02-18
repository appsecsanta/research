// server.js
'use strict';

const path = require('path');
const express = require('express');
const helmet = require('helmet');
const Database = require('better-sqlite3');

const app = express();
const db = new Database(process.env.SQLITE_PATH || path.join(__dirname, 'data', 'app.db'));

db.pragma('journal_mode = WAL');
db.exec(`
  CREATE TABLE IF NOT EXISTS profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    display_name TEXT NOT NULL,
    bio TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
  );
`);

app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

app.use(helmet());
app.use(express.urlencoded({ extended: false, limit: '16kb' }));
app.use(express.json({ limit: '16kb' }));

function normalizeString(value) {
  if (typeof value !== 'string') return '';
  return value.replace(/\s+/g, ' ').trim();
}

app.get('/', (req, res) => {
  res.type('html').send(`
    <!doctype html>
    <html lang="en">
      <head><meta charset="utf-8" /><meta name="viewport" content="width=device-width, initial-scale=1" /><title>Create Profile</title></head>
      <body>
        <h1>Create Profile</h1>
        <form method="post" action="/profile">
          <label>
            Display name<br/>
            <input name="displayName" maxlength="80" required />
          </label>
          <br/><br/>
          <label>
            Bio<br/>
            <textarea name="bio" maxlength="500" required></textarea>
          </label>
          <br/><br/>
          <button type="submit">Save</button>
        </form>
      </body>
    </html>
  `);
});

app.post('/profile', (req, res, next) => {
  try {
    const displayName = normalizeString(req.body.displayName);
    const bio = normalizeString(req.body.bio);

    if (!displayName || displayName.length > 80) {
      return res.status(400).type('text').send('Invalid display name.');
    }
    if (!bio || bio.length > 500) {
      return res.status(400).type('text').send('Invalid bio.');
    }

    const insert = db.prepare('INSERT INTO profiles (display_name, bio) VALUES (?, ?)');
    const info = insert.run(displayName, bio);

    const profile = db
      .prepare('SELECT id, display_name AS displayName, bio, created_at AS createdAt FROM profiles WHERE id = ?')
      .get(info.lastInsertRowid);

    if (!profile) return res.status(500).type('text').send('Failed to load profile.');

    res.status(201).render('profile', { profile });
  } catch (err) {
    next(err);
  }
});

app.use((err, req, res, next) => {
  // eslint-disable-next-line no-console
  console.error(err);
  res.status(500).type('text').send('Internal Server Error');
});

const port = Number(process.env.PORT) || 3000;
app.listen(port, () => {
  // eslint-disable-next-line no-console
  console.log(`Listening on http://localhost:${port}`);
});
