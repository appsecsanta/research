const express = require('express');
const router = express.Router();
const User = require('../models/User'); // Assuming User model is defined in ../models/User

// Middleware to check if user is admin (placeholder; implement actual auth logic)
const isAdmin = (req, res, next) => {
  // Replace with actual authentication check
  if (!req.user || !req.user.isAdmin) {
    return res.status(403).json({ message: 'Access denied: Administrators only' });
  }
  next();
};

router.put('/api/users/:id/role', isAdmin, async (req, res) => {
  try {
    const { role } = req.body;
    if (!role) {
      return res.status(400).json({ message: 'New role is required' });
    }

    const user = await User.findByIdAndUpdate(
      req.params.id,
      { role },
      { new: true, runValidators: true }
    );

    if (!user) {
      return res.status(404).json({ message: 'User not found' });
    }

    res.status(200).json(user);
  } catch (err) {
    console.error(err);
    res.status(500).json({ message: 'Server error' });
  }
});

module.exports = router;
