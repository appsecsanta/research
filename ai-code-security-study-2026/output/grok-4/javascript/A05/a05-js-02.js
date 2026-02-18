const { MongoClient } = require('mongodb');

let cachedDb = null;

async function connectToDatabase(uri, dbName) {
  if (cachedDb) {
    return cachedDb;
  }

  const client = await MongoClient.connect(uri, {
    useNewUrlParser: true,
    useUnifiedTopology: true,
  });

  const db = client.db(dbName);
  cachedDb = db;
  return db;
}

module.exports = connectToDatabase;
