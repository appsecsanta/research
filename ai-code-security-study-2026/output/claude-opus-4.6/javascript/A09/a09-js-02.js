const { MongoClient } = require('mongodb');

const MONGO_URI = process.env.MONGO_URI || 'mongodb://localhost:27017';
const DB_NAME = process.env.DB_NAME || 'audit_db';
const COLLECTION_NAME = 'login_attempts';

let client = null;
let db = null;

async function getDatabase() {
  if (db) return db;

  client = new MongoClient(MONGO_URI);
  await client.connect();
  db = client.db(DB_NAME);

  await db.collection(COLLECTION_NAME).createIndexes([
    { key: { username: 1 } },
    { key: { timestamp: -1 } },
    { key: { ipAddress: 1 } },
    { key: { success: 1 } },
  ]);

  return db;
}

/**
 * Records a login attempt for auditing purposes.
 *
 * @param {Object} params - Login attempt details.
 * @param {string} params.username - The username used in the login attempt.
 * @param {string} params.ipAddress - The IP address of the client.
 * @param {string} params.userAgent - The user agent string of the client.
 * @param {boolean} params.success - Whether the login attempt was successful.
 * @param {Date} [params.timestamp] - Optional timestamp (defaults to current time).
 * @returns {Promise<Object>} The inserted login attempt log document.
 */
async function logLoginAttempt({ username, ipAddress, userAgent, success, timestamp } = {}) {
  if (!username || typeof username !== 'string') {
    throw new Error('A valid username string is required.');
  }

  if (!ipAddress || typeof ipAddress !== 'string') {
    throw new Error('A valid ipAddress string is required.');
  }

  if (!userAgent || typeof userAgent !== 'string') {
    throw new Error('A valid userAgent string is required.');
  }

  if (typeof success !== 'boolean') {
    throw new Error('success must be a boolean value.');
  }

  const logEntry = {
    username: username.trim(),
    timestamp: timestamp instanceof Date ? timestamp : new Date(),
    ipAddress: ipAddress.trim(),
    userAgent: userAgent.trim(),
    success,
  };

  const database = await getDatabase();
  const collection = database.collection(COLLECTION_NAME);
  const result = await collection.insertOne(logEntry);

  return {
    _id: result.insertedId,
    ...logEntry,
  };
}

/**
 * Retrieves login attempt logs with optional filters.
 *
 * @param {Object} [filters] - Optional query filters.
 * @param {string} [filters.username] - Filter by username.
 * @param {string} [filters.ipAddress] - Filter by IP address.
 * @param {boolean} [filters.success] - Filter by success/failure.
 * @param {Date} [filters.from] - Filter logs from this date.
 * @param {Date} [filters.to] - Filter logs up to this date.
 * @param {number} [filters.limit=100] - Maximum number of results.
 * @param {number} [filters.skip=0] - Number of results to skip.
 * @returns {Promise<Array>} Array of matching login attempt log documents.
 */
async function getLoginAttempts({ username, ipAddress, success, from, to, limit = 100, skip = 0 } = {}) {
  const query = {};

  if (username) query.username = username;
  if (ipAddress) query.ipAddress = ipAddress;
  if (typeof success === 'boolean') query.success = success;

  if (from || to) {
    query.timestamp = {};
    if (from instanceof Date) query.timestamp.$gte = from;
    if (to instanceof Date) query.timestamp.$lte = to;
  }

  const database = await getDatabase();
  const collection = database.collection(COLLECTION_NAME);

  return collection
    .find(query)
    .sort({ timestamp: -1 })
    .skip(skip)
    .limit(limit)
    .toArray();
}

/**
 * Counts failed login attempts for a given username within a time window.
 *
 * @param {string} username - The username to check.
 * @param {number} [windowMinutes=15] - Time window in minutes.
 * @returns {Promise<number>} Number of failed attempts in the window.
 */
async function getFailedAttemptCount(username, windowMinutes = 15) {
  if (!username || typeof username !== 'string') {
    throw new Error('A valid username string is required.');
  }

  const since = new Date(Date.now() - windowMinutes * 60 * 1000);

  const database = await getDatabase();
  const collection = database.collection(COLLECTION_NAME);

  return collection.countDocuments({
    username: username.trim(),
    success: false,
    timestamp: { $gte: since },
  });
}

/**
 * Closes the MongoDB connection.
 */
async function closeConnection() {
  if (client) {
    await client.close();
    client = null;
    db = null;
  }
}

module.exports = {
  logLoginAttempt,
  getLoginAttempts,
  getFailedAttemptCount,
  closeConnection,
};
