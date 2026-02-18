const { MongoClient } = require('mongodb');

async function logLoginAttempt(username, ipAddress, userAgent, success) {
    const uri = "mongodb://localhost:27017";
    const client = new MongoClient(uri);

    try {
        await client.connect();
        const database = client.db('auditLogs');
        const collection = database.collection('loginAttempts');

        const logEntry = {
            username,
            timestamp: new Date(),
            ipAddress,
            userAgent,
            success
        };

        await collection.insertOne(logEntry);
    } finally {
        await client.close();
    }
}
