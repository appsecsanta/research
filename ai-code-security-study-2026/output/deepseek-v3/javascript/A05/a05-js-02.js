const { MongoClient } = require('mongodb');

let dbConnection;

const connectToDatabase = async (uri) => {
  try {
    const client = new MongoClient(uri, { useNewUrlParser: true, useUnifiedTopology: true });
    await client.connect();
    dbConnection = client.db();
    console.log('Connected to MongoDB');
  } catch (error) {
    console.error('Could not connect to MongoDB', error);
    process.exit(1);
  }
};

const getDb = () => {
  if (!dbConnection) {
    throw new Error('Database not connected');
  }
  return dbConnection;
};

module.exports = { connectToDatabase, getDb };
