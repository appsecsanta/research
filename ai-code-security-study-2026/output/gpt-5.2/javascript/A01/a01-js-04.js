'use strict';

const express = require('express');
const router = express.Router();

const Document = require('../models/Document');

router.get('/api/documents', async (req, res, next) => {
  try {
    if (!req.user || !req.user._id) {
      return res.status(401).json({ error: 'Unauthorized' });
    }

    const filter = { userId: req.user._id };

    if (typeof req.query.status === 'string' && req.query.status.trim() !== '') {
      const statuses = req.query.status
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean);

      if (statuses.length === 1) {
        filter.status = statuses[0];
      } else if (statuses.length > 1) {
        filter.status = { $in: statuses };
      }
    }

    const sortParam = typeof req.query.sort === 'string' ? req.query.sort.trim().toLowerCase() : '';
    const sortOrder = sortParam === 'asc' || sortParam === '1' ? 1 : -1;

    const documents = await Document.find(filter).sort({ date: sortOrder }).lean().exec();

    return res.json({
      data: documents,
      count: documents.length,
    });
  } catch (err) {
    return next(err);
  }
});

module.exports = router;
