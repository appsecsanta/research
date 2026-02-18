const express = require('express');
const mongoose = require('mongoose');
const authenticate = require('./authenticate');

const router = express.Router();
const User = mongoose.model('User', new mongoose.Schema({
  name: String,
  email: String
}));

router.get('/api/users/:id', authenticate, async (req, res) => {
  try {
    const user = await User.findById(req.params.id).select('-password');
    if (!user) return res.status(404).json({ message: 'User not found' });
    res.json(user);
  } catch (error) {
    res.status(500).json({ message: 'Failed to fetch user' });
  }
});

module.exports = router;
