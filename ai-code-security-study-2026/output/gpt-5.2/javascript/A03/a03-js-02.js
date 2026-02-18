'use strict';

const express = require('express');
const { Pool } = require('pg');

const app = express();

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: process.env.PGSSLMODE === 'require' ? { rejectUnauthorized: false } : undefined,
});

app.get('/api/products/search', async (req, res) => {
  const q = typeof req.query.q === 'string' ? req.query.q.trim() : '';

  if (!q) {
    return res.status(400).json({ error: 'Missing or empty query parameter "q".' });
  }

  const limit = Number.isFinite(Number(req.query.limit))
    ? Math.min(Math.max(parseInt(req.query.limit, 10), 1), 100)
    : 50;

  const offset = Number.isFinite(Number(req.query.offset))
    ? Math.max(parseInt(req.query.offset, 10), 0)
    : 0;

  const search = `%${q.replace(/[%_\\]/g, '\\$&')}%`;

  const sql = `
    SELECT id, name, description, price, created_at, updated_at
    FROM products
    WHERE (name ILIKE $1 ESCAPE '\\' OR description ILIKE $1 ESCAPE '\\')
    ORDER BY name ASC
    LIMIT $2 OFFSET $3;
  `;

  try {
    const { rows } = await pool.query(sql, [search, limit, offset]);
    res.json({ query: q, count: rows.length, results: rows });
  } catch (err) {
    res.status(500).json({ error: 'Database query failed.' });
  }
});

module.exports = app;
