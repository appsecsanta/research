const crypto = require('crypto');
const express = require('express');
const app = express();

const generateToken = () => {
  return crypto.randomBytes(32).toString('hex');
};

const tokens = new Set();

app.get('/verify', (req, res) => {
  const { token } = req.query;

  if (!token) {
    return res.status(400).json({ error: 'Token is required' });
  }

  if (tokens.has(token)) {
    tokens.delete(token);
    return res.status(200).json({ message: 'Email verified successfully' });
  }

  return res.status(404).json({ error: 'Invalid or expired token' });
});

app.post('/register', (req, res) => {
  const token = generateToken();
  tokens.add(token);
  // Send email with verification link
  res.status(201).json({ token });
});

const PORT = 3000;
app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
