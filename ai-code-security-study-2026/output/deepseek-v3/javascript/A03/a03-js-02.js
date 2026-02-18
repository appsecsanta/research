const express = require('express');
const { Pool } = require('pg');

const app = express();
const pool = new Pool({
  user: 'your_db_user',
  host: 'localhost',
  database: 'your_db_name',
  password: 'your_db_password',
  port: 5432,
});

app.get('/api/products/search', async (req, res) => {
  const { query } = req.query;

  if (!query) {
    return res.status(400).json({ error: 'Search query is required' });
  }

  try {
    const searchQuery = `
      SELECT * FROM products 
      WHERE name ILIKE $1 OR description ILIKE $1
    `;
    const searchValue = `%${query}%`;
    const { rows } = await pool.query(searchQuery, [searchValue]);

    res.json(rows);
  } catch (error) {
    console.error('Error searching products:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Server is running on port ${PORT}`);
});
