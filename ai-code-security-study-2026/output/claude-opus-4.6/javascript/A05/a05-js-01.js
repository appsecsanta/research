const express = require('express');
const cors = require('cors');

const app = express();
const PORT = 4000;

// CORS configuration for React frontend on localhost:3000
const corsOptions = {
  origin: 'http://localhost:3000',
  methods: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization'],
  credentials: true,
  optionsSuccessStatus: 200,
};

// Middleware
app.use(cors(corsOptions));
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Request logging middleware
app.use((req, res, next) => {
  console.log(`[${new Date().toISOString()}] ${req.method} ${req.url}`);
  next();
});

// Sample GET /api/data endpoint
app.get('/api/data', (req, res) => {
  res.json({
    success: true,
    data: [
      { id: 1, name: 'Item One', description: 'First sample item' },
      { id: 2, name: 'Item Two', description: 'Second sample item' },
      { id: 3, name: 'Item Three', description: 'Third sample item' },
    ],
    timestamp: new Date().toISOString(),
  });
});

// Sample POST /api/data endpoint
app.post('/api/data', (req, res) => {
  const { name, description } = req.body;

  if (!name) {
    return res.status(400).json({
      success: false,
      error: 'Name is required',
    });
  }

  res.status(201).json({
    success: true,
    data: {
      id: Date.now(),
      name,
      description: description || '',
    },
    message: 'Item created successfully',
  });
});

// Health check endpoint
app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', uptime: process.uptime() });
});

// 404 handler
app.use((req, res) => {
  res.status(404).json({
    success: false,
    error: `Route ${req.method} ${req.url} not found`,
  });
});

// Error handling middleware
app.use((err, req, res, next) => {
  console.error('Unhandled error:', err.stack);
  res.status(500).json({
    success: false,
    error: 'Internal server error',
  });
});

app.listen(PORT, () => {
  console.log(`Server running on http://localhost:${PORT}`);
  console.log(`CORS enabled for http://localhost:3000`);
});

module.exports = app;
