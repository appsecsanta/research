const express = require('express');
const cookieParser = require('cookie-parser');
const crypto = require('crypto');
const mongoose = require('mongoose');
const bcrypt = require('bcryptjs');

// Connect to MongoDB (replace with your connection string)
mongoose.connect('mongodb://localhost:27017/remembermeDB', { useNewUrlParser: true, useUnifiedTopology: true });

// User Schema
const userSchema = new mongoose.Schema({
  username: { type: String, required: true, unique: true },
  password: { type: String, required: true },
  rememberToken: { type: String, default: null },
  tokenExpiry: { type: Date, default: null }
});

const User = mongoose.model('User', userSchema);

const app = express();
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(cookieParser());

// Middleware to check remember me cookie
const checkRememberMe = async (req, res, next) => {
  const token = req.cookies.rememberMe;
  if (token) {
    try {
      const user = await User.findOne({
        rememberToken: token,
        tokenExpiry: { $gt: new Date() }
      });
      if (user) {
        req.user = user; // Attach user to request for session
        console.log(`Auto-logged in user: ${user.username}`);
      }
    } catch (err) {
      console.error('Error checking remember me:', err);
    }
  }
  next();
};

app.use(checkRememberMe);

// Login route
app.post('/login', async (req, res) => {
  const { username, password, rememberMe } = req.body;

  try {
    const user = await User.findOne({ username });
    if (!user || !(await bcrypt.compare(password, user.password))) {
      return res.status(401).json({ message: 'Invalid credentials' });
    }

    if (rememberMe) {
      // Generate persistent token
      const token = crypto.randomBytes(64).toString('hex');
      const expiry = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000); // 30 days

      user.rememberToken = token;
      user.tokenExpiry = expiry;
      await user.save();

      // Set cookie (secure in production)
      res.cookie('rememberMe', token, {
        httpOnly: true,
        secure: process.env.NODE_ENV === 'production',
        maxAge: 30 * 24 * 60 * 60 * 1000 // 30 days
      });
    }

    // Simulate session login (in real app, use sessions)
    req.user = user;
    res.json({ message: 'Logged in successfully' });
  } catch (err) {
    console.error('Login error:', err);
    res.status(500).json({ message: 'Server error' });
  }
});

// Logout route (clear remember me if needed)
app.post('/logout', async (req, res) => {
  if (req.cookies.rememberMe) {
    const token = req.cookies.rememberMe;
    await User.updateOne({ rememberToken: token }, { rememberToken: null, tokenExpiry: null });
    res.clearCookie('rememberMe');
  }
  res.json({ message: 'Logged out' });
});

// Protected route example
app.get('/protected', (req, res) => {
  if (!req.user) {
    return res.status(401).json({ message: 'Unauthorized' });
  }
  res.json({ message: `Hello, ${req.user.username}` });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`Server running on port ${PORT}`));
