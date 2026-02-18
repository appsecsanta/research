const express = require('express');
const mongoose = require('mongoose');
const router = express.Router();

const Account = mongoose.model('Account', new mongoose.Schema({
    userId: String,
    balance: Number
}));

router.post('/api/transfer', async (req, res) => {
    const { fromAccountId, toAccountId, amount } = req.body;

    if (!fromAccountId || !toAccountId || !amount || amount <= 0) {
        return res.status(400).json({ message: 'Invalid input' });
    }

    const session = await mongoose.startSession();
    session.startTransaction();

    try {
        const fromAccount = await Account.findById(fromAccountId).session(session);
        const toAccount = await Account.findById(toAccountId).session(session);

        if (!fromAccount || !toAccount) {
            await session.abortTransaction();
            session.endSession();
            return res.status(404).json({ message: 'Account not found' });
        }

        if (fromAccount.balance < amount) {
            await session.abortTransaction();
            session.endSession();
            return res.status(400).json({ message: 'Insufficient funds' });
        }

        fromAccount.balance -= amount;
        toAccount.balance += amount;

        await fromAccount.save({ session });
        await toAccount.save({ session });

        await session.commitTransaction();
        session.endSession();

        res.status(200).json({ message: 'Transfer successful' });
    } catch (error) {
        await session.abortTransaction();
        session.endSession();
        res.status(500).json({ message: 'Transfer failed', error: error.message });
    }
});

module.exports = router;
