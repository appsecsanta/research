const express = require('express');
const cors = require('cors');

const app = express();
const port = 4000;

// Enable CORS for requests from localhost:3000
app.use(cors({
  origin: 'http://localhost:3000',
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization']
}));

// Parse JSON bodies
app.use(express.json());

// Sample endpoint
app.get('/api/data', (req, res) => {
  res.json({ message: 'Hello from the API!', data: [1, 2, 3] });
});

// Start the server
app.listen(port, () => {
  console.log(`Server running on http://localhost:${port}`);
});
