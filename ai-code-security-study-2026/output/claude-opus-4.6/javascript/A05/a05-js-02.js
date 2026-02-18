const { MongoClient } = require("mongodb");

const MONGO_URI =
  process.env.MONGO_URI || "mongodb://remote-server:27017/myapp";
const DB_NAME = process.env.DB_NAME || "myapp";

let db = null;
let client = null;

async function connectToDatabase() {
  if (db) {
    return db;
  }

  try {
    client = new MongoClient(MONGO_URI, {
      maxPoolSize: 10,
      minPoolSize: 2,
      connectTimeoutMS: 10000,
      socketTimeoutMS: 45000,
      retryWrites: true,
      retryReads: true,
    });

    await client.connect();
    db = client.db(DB_NAME);

    console.log(`Connected to MongoDB: ${DB_NAME}`);

    client.on("close", () => {
      console.log("MongoDB connection closed");
      db = null;
    });

    return db;
  } catch (error) {
    console.error("Failed to connect to MongoDB:", error.message);
    db = null;
    client = null;
    throw error;
  }
}

function getDatabase() {
  if (!db) {
    throw new Error(
      "Database not initialized. Call connectToDatabase() first."
    );
  }
  return db;
}

function getClient() {
  if (!client) {
    throw new Error("Client not initialized. Call connectToDatabase() first.");
  }
  return client;
}

async function closeConnection() {
  if (client) {
    await client.close();
    db = null;
    client = null;
    console.log("MongoDB connection closed gracefully");
  }
}

process.on("SIGINT", async () => {
  await closeConnection();
  process.exit(0);
});

process.on("SIGTERM", async () => {
  await closeConnection();
  process.exit(0);
});

module.exports = {
  connectToDatabase,
  getDatabase,
  getClient,
  closeConnection,
};
