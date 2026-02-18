'use strict';

const express = require('express');
const mongoose = require('mongoose');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');

const app = express();
app.use(express.json({ limit: '10kb' }));

// ---- MongoDB / Mongoose ----
const { MONGODB_URI, JWT_SECRET, JWT_EXPIRES_IN } = process.env;

if (!MONGODB_URI) throw new Error('Missing env: MONGODB_URI');
if (!JWT_SECRET) throw new Error('Missing env: JWT_SECRET');

mongoose.set('strictQuery', true);
mongoose
  .connect(MONGODB_URI)
  .catch((err) => {
    // eslint-disable-next-line no-console
    console.error('MongoDB connection error:', err);
    process.exit(1);
  });

const userSchema = new mongoose.Schema(
  {
    email: { type: String, required: true, unique: true, index: true, trim: true, lowercase: true },
    passwordHash: { type: String, required: true, select: false },
    role: { type: String, required: true, default: 'user' },
  },
  { timestamps: true }
);

const User = mongoose.models.User || mongoose.model('User', userSchema);

// ---- Helpers ----
function isValidEmail(email) {
  if (typeof email !== 'string') return false;
  const e = email.trim().toLowerCase();
  return e.length <= 254 && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e);
}

function isValidPassword(password) {
  return typeof password === 'string' && password.length >= 1 && password.length <= 1024;
}

// ---- Endpoint ----
app.post('/api/login', async (req, res) => {
  try {
    const email = typeof req.body?.email === 'string' ? req.body.email.trim().toLowerCase() : '';
    const password = req.body?.password;

    if (!isValidEmail(email) || !isValidPassword(password)) {
      return res.status(400).json({ error: 'Invalid email or password' });
    }

    const user = await User.findOne({ email }).select('+passwordHash role');
    if (!user) {
      return res.status(401).json({ error: 'Invalid email or password' });
    }

    const ok = await bcrypt.compare(password, user.passwordHash);
    if (!ok) {
      return res.status(401).json({ error: 'Invalid email or password' });
    }

    const payload = {
      userId: String(user._id),
      role: user.role,
    };

    const token = jwt.sign(payload, JWT_SECRET, {
      expiresIn: JWT_EXPIRES_IN || '1h',
    });

    return res.status(200).json({ token });
  } catch (err) {
    // eslint-disable-next-line no-console
    console.error(err);
    return res.status(500).json({ error: 'Internal server error' });
  }
});

module.exports = app;
