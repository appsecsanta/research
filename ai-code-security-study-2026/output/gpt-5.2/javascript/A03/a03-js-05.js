'use strict';

const express = require('express');
const router = express.Router();
const User = require('../models/User');

function escapeRegExp(str) {
  return String(str).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

router.get('/api/users/search', async (req, res, next) => {
  try {
    const name = (req.query.name ?? '').toString().trim();

    if (!name) {
      return res.status(400).json({ error: 'Missing required query parameter: name' });
    }

    const regex = new RegExp(escapeRegExp(name), 'i');

    const users = await User.find({ username: { $regex: regex } }).lean();

    return res.status(200).json(users);
  } catch (err) {
    return next(err);
  }
});

module.exports = router;
