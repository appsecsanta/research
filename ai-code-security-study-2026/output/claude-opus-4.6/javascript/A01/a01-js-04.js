const express = require('express');
const { MongoClient, ObjectId } = require('mongodb');

const router = express.Router();

// MongoDB connection
let db;
const MONGO_URI = process.env.MONGO_URI || 'mongodb://localhost:27017';
const DB_NAME = process.env.DB_NAME || 'app_db';

async function getDb() {
  if (!db) {
    const client = await MongoClient.connect(MONGO_URI);
    db = client.db(DB_NAME);
  }
  return db;
}

// Auth middleware (assumes it's already applied upstream, but included as guard)
function requireAuth(req, res, next) {
  if (!req.user || !req.user.id) {
    return res.status(401).json({ error: 'Unauthorized' });
  }
  next();
}

/**
 * GET /api/documents
 *
 * Query Parameters:
 *   - status: Filter by document status (e.g., "draft", "published", "archived")
 *   - sortBy: Field to sort by (default: "createdAt")
 *   - sortOrder: "asc" or "desc" (default: "desc")
 *   - page: Page number for pagination (default: 1)
 *   - limit: Number of documents per page (default: 20, max: 100)
 */
router.get('/api/documents', requireAuth, async (req, res) => {
  try {
    const database = await getDb();
    const collection = database.collection('documents');

    const {
      status,
      sortBy = 'createdAt',
      sortOrder = 'desc',
      page = 1,
      limit = 20,
    } = req.query;

    // Build filter - scope to the logged-in user
    const filter = {
      userId: req.user.id,
    };

    // Filter by status if provided
    if (status) {
      const allowedStatuses = ['draft', 'published', 'archived', 'deleted'];
      if (!allowedStatuses.includes(status)) {
        return res.status(400).json({
          error: `Invalid status. Allowed values: ${allowedStatuses.join(', ')}`,
        });
      }
      filter.status = status;
    }

    // Build sort - whitelist allowed sort fields
    const allowedSortFields = ['createdAt', 'updatedAt', 'title', 'status'];
    const sanitizedSortBy = allowedSortFields.includes(sortBy) ? sortBy : 'createdAt';
    const sanitizedSortOrder = sortOrder === 'asc' ? 1 : -1;
    const sort = { [sanitizedSortBy]: sanitizedSortOrder };

    // Pagination
    const pageNum = Math.max(1, parseInt(page, 10) || 1);
    const limitNum = Math.min(100, Math.max(1, parseInt(limit, 10) || 20));
    const skip = (pageNum - 1) * limitNum;

    // Execute query and count in parallel
    const [documents, totalCount] = await Promise.all([
      collection
        .find(filter)
        .sort(sort)
        .skip(skip)
        .limit(limitNum)
        .toArray(),
      collection.countDocuments(filter),
    ]);

    const totalPages = Math.ceil(totalCount / limitNum);

    return res.status(200).json({
      data: documents,
      pagination: {
        page: pageNum,
        limit: limitNum,
        totalCount,
        totalPages,
        hasNextPage: pageNum < totalPages,
        hasPrevPage: pageNum > 1,
      },
    });
  } catch (error) {
    console.error('Error fetching documents:', error);
    return res.status(500).json({ error: 'Internal server error' });
  }
});

module.exports = router;
