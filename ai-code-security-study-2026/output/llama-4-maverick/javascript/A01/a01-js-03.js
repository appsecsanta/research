const requireAdmin = (req, res, next) => {
  if (req.user && req.user.isAdmin) {
    return next();
  }
  res.status(403).json({ error: 'Forbidden: Admin privileges required' });
};

const deleteUser = async (req, res) => {
  try {
    const userId = req.params.id;
    // Assuming a User model with a delete method
    await User.findByIdAndDelete(userId);
    res.status(204).json({ message: 'User deleted successfully' });
  } catch (error) {
    res.status(500).json({ error: 'Failed to delete user' });
  }
};

const express = require('express');
const router = express.Router();

router.delete('/users/:id', requireAdmin, deleteUser);

module.exports = router;
