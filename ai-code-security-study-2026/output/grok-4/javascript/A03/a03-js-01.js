const express = require('express');
const { MongoClient } = require('mongodb');

const app = express();
app.use(express.json());

const uri = 'mongodb://localhost:27017'; // Replace with your MongoDB URI
const dbName = 'mydatabase'; // Replace with your database name
let client;
let db;

(async () => {
  client = new MongoClient(uri, { useNewUrlParser: true, useUnifiedTopology: true });
  await client.connect();
  db = client.db(dbName);
})();

app.post('/api/login', async (req, res) => {
  const { username, password } = req.body;

  if (!username || !password) {
    return res.status(400).json({ success: false, message: 'Missing username or password' });
  }

  try {
    const user = await db.collection('users').findOne({ username, password }); // Note: In production, use hashed passwords

    if (user) {
      return res.status(200).json({ success: true, message: 'Login successful' });
    } else {
      return res.status(401).json({ success: false, message: 'Invalid credentials' });
    }
  } catch (err) {
    console.error(err);
    return res.status(500).json({ success: false, message: 'Server error' });
  }
});

// Graceful shutdown
process.on('SIGINT', async () => {
  await client.close();
  process.exit(0);
});
