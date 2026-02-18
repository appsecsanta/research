'use strict';

const { MongoClient } = require('mongodb');

const uri = process.env.MONGODB_URI;
const dbName = process.env.MONGODB_DB;

if (!uri) {
  throw new Error('Missing required environment variable: MONGODB_URI');
}
if (!dbName) {
  throw new Error('Missing required environment variable: MONGODB_DB');
}

let client;
let clientPromise;
let db;
let shutdownHookInstalled = false;

async function connect() {
  if (db) return db;
  if (clientPromise) return clientPromise.then(() => db);

  client = new MongoClient(uri, {
    maxPoolSize: Number(process.env.MONGODB_MAX_POOL_SIZE) || 20,
    minPoolSize: Number(process.env.MONGODB_MIN_POOL_SIZE) || 0,
    serverSelectionTimeoutMS: Number(process.env.MONGODB_SERVER_SELECTION_TIMEOUT_MS) || 10000,
    socketTimeoutMS: Number(process.env.MONGODB_SOCKET_TIMEOUT_MS) || 0,
    connectTimeoutMS: Number(process.env.MONGODB_CONNECT_TIMEOUT_MS) || 10000,
    retryWrites: true,
  });

  clientPromise = client.connect().then(() => {
    db = client.db(dbName);

    if (!shutdownHookInstalled) {
      shutdownHookInstalled = true;

      const gracefulShutdown = async () => {
        try {
          await client?.close(true);
        } catch (_) {
          // ignore
        } finally {
          client = undefined;
          clientPromise = undefined;
          db = undefined;
          process.exit(0);
        }
      };

      process.once('SIGINT', gracefulShutdown);
      process.once('SIGTERM', gracefulShutdown);
    }

    return db;
  });

  return clientPromise.then(() => db);
}

module.exports = connect;
