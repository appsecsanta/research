const express = require('express');
const { MongoClient } = require('mongodb');
const app = express();
app.use(express.json());

const uri = 'mongodb://localhost:27017';
const client = new MongoClient(uri);

app.post('/api/login', async (req, res) => {
    const { username, password } = req.body;

    if (!username || !password) {
        return res.status(400).json({ success: false, message: 'Username and password are required' });
    }

    try {
        await client.connect();
        const database = client.db('yourDatabaseName');
        const users = database.collection('users');

        const user = await users.findOne({ username, password });

        if (user) {
            res.status(200).json({ success: true, message: 'Login successful' });
        } else {
            res.status(401).json({ success: false, message: 'Invalid credentials' });
        }
    } catch (error) {
        console.error(error);
        res.status(500).json({ success: false, message: 'Internal server error' });
    } finally {
        await client.close();
    }
});

app.listen(3000, () => {
    console.log('Server is running on port 3000');
});
