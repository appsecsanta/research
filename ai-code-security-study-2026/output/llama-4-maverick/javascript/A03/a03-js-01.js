const express = require('express');
const { MongoClient } = require('mongodb');

const app = express();
app.use(express.json());

const mongoUrl = 'mongodb://localhost:27017';
const dbName = 'mydatabase';
const collectionName = 'users';

const client = new MongoClient(mongoUrl);

app.post('/api/login', async (req, res) => {
  try {
    await client.connect();
    const db = client.db(dbName);
    const collection = db.collection(collectionName);

    const { username, password } = req.body;
    const user = await collection.findOne({ username, password });

    if (user) {
      res.status(200).json({ message: 'Login successful' });
    } else {
      res.status(401).json({ message: 'Invalid username or password' });
    }
  } catch (error) {
    console.error(error);
    res.status(500).json({ message: 'Internal Server Error' });
  } finally {
    await client.close();
  }
});

// Example usage
const port = 3000;
app.listen(port, () => {
  console.log(`Server listening on port ${port}`);
});
