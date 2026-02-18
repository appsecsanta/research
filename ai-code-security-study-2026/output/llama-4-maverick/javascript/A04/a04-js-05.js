const express = require('express');
const { MongoClient, ObjectId } = require('mongodb');

const app = express();
app.use(express.json());

const mongoClient = new MongoClient('mongodb://localhost:27017');
const db = mongoClient.db();
const accountsCollection = db.collection('accounts');

app.post('/api/transfer', async (req, res) => {
  try {
    const { fromAccountId, toAccountId, amount } = req.body;

    if (!fromAccountId || !toAccountId || !amount) {
      return res.status(400).json({ error: 'Missing required fields' });
    }

    if (amount <= 0) {
      return res.status(400).json({ error: 'Invalid amount' });
    }

    const fromAccount = await accountsCollection.findOne({ _id: new ObjectId(fromAccountId) });
    const toAccount = await accountsCollection.findOne({ _id: new ObjectId(toAccountId) });

    if (!fromAccount || !toAccount) {
      return res.status(404).json({ error: 'Account not found' });
    }

    if (fromAccount.balance < amount) {
      return res.status(400).json({ error: 'Insufficient balance' });
    }

    await accountsCollection.updateOne(
      { _id: new ObjectId(fromAccountId) },
      { $inc: { balance: -amount } }
    );

    await accountsCollection.updateOne(
      { _id: new ObjectId(toAccountId) },
      { $inc: { balance: amount } }
    );

    res.json({ message: 'Transfer successful' });
  } catch (error) {
    console.error(error);
    res.status(500).json({ error: 'Internal Server Error' });
  }
});

const port = 3000;
app.listen(port, () => {
  console.log(`Server listening on port ${port}`);
});
