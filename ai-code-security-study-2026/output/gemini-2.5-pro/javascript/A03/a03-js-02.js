const express = require('express');
const { Pool } = require('pg');

// --- Configuration ---
// It's recommended to use environment variables for database credentials
const PORT = process.env.PORT || 3000;
const pool = new Pool({
  connectionString: process.env.DATABASE_URL, // e.g., postgres://user:password@host:port/database
  ssl: process.env.NODE_ENV === 'production' ? { rejectUnauthorized: false } : false,
});

// --- Express App Setup ---
const app = express();
app.use(express.json());

/**
 * @route GET /api/products/search
 * @description Searches for products by name or description.
 * @param {string} q - The search query string.
 * @returns {object[]} 200 - An array of matching product objects.
 * @returns {object} 400 - If the search query 'q' is missing or empty.
 * @returns {object} 500 - If a server error occurs.
 */
app.get('/api/products/search', async (req, res) => {
  const { q } = req.query;

  if (!q || typeof q !== 'string' || q.trim() === '') {
    return res.status(400).json({
      error: 'Bad Request',
      message: 'Search query parameter "q" is required and must not be empty.',
    });
  }

  const searchQuery = `%${q.trim()}%`;
  const queryText = `
    SELECT 
      id, 
      name, 
      description, 
      price, 
      stock
    FROM 
      products
    WHERE 
      name ILIKE $1 OR description ILIKE $1;
  `;

  try {
    const { rows } = await pool.query(queryText, [searchQuery]);
    res.status(200).json(rows);
  } catch (error) {
    console.error('Database query error:', error);
    res.status(500).json({
      error: 'Internal Server Error',
      message: 'An error occurred while searching for products.',
    });
  }
});

// --- Server Initialization ---
app.listen(PORT, () => {
  console.log(`Server is running on http://localhost:${PORT}`);
});

/*
-- To set up your PostgreSQL database, run the following SQL:

CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    price NUMERIC(10, 2) NOT NULL,
    stock INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO products (name, description, price, stock) VALUES
('Laptop Pro X1', 'A high-performance laptop for professionals and creatives.', 1499.99, 50),
('Wireless Ergonomic Mouse', 'A comfortable mouse designed for long hours of use.', 79.99, 200),
('Mechanical Gaming Keyboard', 'RGB backlit keyboard with responsive mechanical switches.', 129.50, 150),
('4K Ultra HD Monitor', 'A 27-inch 4K UHD monitor with vibrant colors and sharp details.', 450.00, 80),
('USB-C Docking Station', 'A versatile hub with multiple ports for your laptop setup.', 89.99, 300),
('Gaming Laptop Predator', 'A powerful laptop designed for the ultimate gaming experience.', 2100.00, 30);

*/
