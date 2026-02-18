// verifyService.js
import { db } from './db.js'; // assuming you have a db module

const verifyToken = async (token) => {
    const tokenDoc = await db.collection('tokens').findOne({ token, used: false });
    if (!tokenDoc) {
        throw new Error('Invalid or expired token');
    }

    await db.collection('users').updateOne({ _id: tokenDoc.userId }, { $set: { verified: true } });
    await db.collection('tokens').updateOne({ _id: tokenDoc._id }, { $set: { used: true } });
};

export { verifyToken };
