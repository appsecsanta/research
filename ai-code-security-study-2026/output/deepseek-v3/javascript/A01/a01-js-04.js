const express = require('express');
const mongoose = require('mongoose');
const router = express.Router();

const Document = mongoose.model('Document', new mongoose.Schema({
  title: String,
  content: String,
  status: String,
  createdAt: Date,
  userId: mongoose.Schema.Types.ObjectId
}));

router.get('/api/documents', async (req, res) => {
  try {
    const { status, sort } = req.query;
    const userId = req.user._id;

    let query = { userId };
    if (status) {
      query.status = status;
    }

    let sortOptions = {};
    if (sort === 'asc') {
      sortOptions.createdAt = 1;
    } else if (sort === 'desc') {
      sortOptions.createdAt = -1;
    }

    const documents = await Document.find(query).sort(sortOptions);
    res.json(documents);
  } catch (error) {
    res.status(500).json({ message: 'Server error', error: error.message });
  }
});

module.exports = router;
