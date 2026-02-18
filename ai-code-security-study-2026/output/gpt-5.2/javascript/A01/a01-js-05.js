const express = require('express');
const User = require('../models/User');

const router = express.Router();

const authenticate = (req, res, next) => {
  if (!req.user) return res.status(401).json({ error: 'Unauthorized' });
  next();
};

const requireAdmin = (req, res, next) => {
  if (req.user?.role !== 'admin') return res.status(403).json({ error: 'Forbidden' });
  next();
};

const asyncHandler =
  (fn) =>
  (req, res, next) =>
    Promise.resolve(fn(req, res, next)).catch(next);

const getAllowedRoles = () => {
  const path = User?.schema?.path?.('role');
  const enumValues = path?.enumValues;
  return Array.isArray(enumValues) && enumValues.length ? enumValues : null;
};

router.put(
  '/api/users/:id/role',
  authenticate,
  requireAdmin,
  asyncHandler(async (req, res) => {
    const { id } = req.params;
    const role = typeof req.body?.role === 'string' ? req.body.role.trim() : '';

    if (!role) return res.status(400).json({ error: 'Role is required' });

    const allowedRoles = getAllowedRoles();
    if (allowedRoles && !allowedRoles.includes(role)) {
      return res.status(400).json({ error: 'Invalid role' });
    }

    let updatedUser;
    try {
      updatedUser = await User.findByIdAndUpdate(
        id,
        { $set: { role } },
        { new: true, runValidators: true, context: 'query' }
      ).select('-password -__v');
    } catch (err) {
      if (err?.name === 'CastError') return res.status(400).json({ error: 'Invalid user id' });
      if (err?.name === 'ValidationError') return res.status(400).json({ error: err.message });
      throw err;
    }

    if (!updatedUser) return res.status(404).json({ error: 'User not found' });

    res.status(200).json({ user: updatedUser });
  })
);

module.exports = router;
