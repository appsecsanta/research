const express = require('express');
const { MongoClient, ObjectId } = require('mongodb');

const router = express.Router();
const mongoClient = new MongoClient(process.env.MONGODB_URI);

router.get('/api/documents', async (req, res) => {
  try {
    const db = mongoClient.db();
    const documentsCollection = db.collection('documents');

    const { status, sortByDate } = req.query;
    const filter = { userId: req.user._id };

    if (status) {
      filter.status = status;
    }

    const sort = {};
    if (sortByDate) {
      sort.createdAt = sortByDate === 'asc' ? 1 : -1;
    } else {
      sort.createdAt = -1;
    }

    const documents = await documentsCollection.find(filter).sort(sort).toArray();
    res.json(documents);
  } catch (error) {
    console.error(error);
    res.status(500).json({ message: 'Failed to retrieve documents' });
  }
});

module.exports = router;
