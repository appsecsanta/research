// lib/mongo.js

const { MongoClient } = require('mongodb');

const uri = process.env.MONGO_URI;
const dbName = process.env.MONGO_DB_NAME;

if (!uri) {
  throw new Error('The MONGO_URI environment variable must be defined.');
}

if (!dbName) {
  throw new Error('The MONGO_DB_NAME environment variable must be defined.');
}

/**
 * A cached connection promise.
 * By caching the promise, we prevent multiple connection attempts while one is in progress.
 * @type {Promise<import('mongodb').Db> | null}
 */
let cachedDbPromise = null;

/**
 * A global MongoClient instance.
 * @type {MongoClient}
 */
const client = new MongoClient(uri);

/**
 * Connects to the MongoDB database and returns the database instance.
 * It implements a singleton pattern to ensure a single, shared connection.
 *
 * @returns {Promise<import('mongodb').Db>} A promise that resolves to the database instance.
 */
async function getDb() {
  if (cachedDbPromise) {
    return cachedDbPromise;
  }

  try {
    // Create a new promise for the connection
    cachedDbPromise = client.connect().then((connectedClient) => {
      console.log('Successfully connected to MongoDB.');
      
      // Add a listener for the 'close' event
      connectedClient.on('close', () => {
        console.log('MongoDB connection closed.');
        cachedDbPromise = null; // Reset cache on close
      });

      return connectedClient.db(dbName);
    });

    return await cachedDbPromise;
  } catch (error) {
    console.error('Failed to connect to MongoDB:', error);
    // If connection fails, reset the promise to allow for future retry attempts.
    cachedDbPromise = null;
    // Re-throw the error to be handled by the calling function.
    throw error;
  }
}

module.exports = getDb;
