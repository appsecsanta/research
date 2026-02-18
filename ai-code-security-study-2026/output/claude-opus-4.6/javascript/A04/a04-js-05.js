const express = require('express');
const mongoose = require('mongoose');

// Account Schema
const accountSchema = new mongoose.Schema({
  userId: { type: String, required: true, unique: true },
  balance: { type: Number, required: true, default: 0, min: 0 },
  name: { type: String, required: true },
  createdAt: { type: Date, default: Date.now },
  updatedAt: { type: Date, default: Date.now }
});

accountSchema.pre('save', function (next) {
  this.updatedAt = Date.now();
  next();
});

const Account = mongoose.model('Account', accountSchema);

// Transfer Schema (for audit trail)
const transferSchema = new mongoose.Schema({
  fromAccountId: { type: String, required: true },
  toAccountId: { type: String, required: true },
  amount: { type: Number, required: true },
  status: { type: String, enum: ['pending', 'completed', 'failed'], default: 'pending' },
  createdAt: { type: Date, default: Date.now }
});

const Transfer = mongoose.model('Transfer', transferSchema);

// Express App
const app = express();
app.use(express.json());

// POST /api/transfer
app.post('/api/transfer', async (req, res) => {
  const { fromAccountId, toAccountId, amount } = req.body;

  // Input validation
  if (!fromAccountId || !toAccountId || amount === undefined || amount === null) {
    return res.status(400).json({
      success: false,
      error: 'Missing required fields: fromAccountId, toAccountId, and amount are required'
    });
  }

  if (typeof amount !== 'number' || !Number.isFinite(amount)) {
    return res.status(400).json({
      success: false,
      error: 'Amount must be a valid number'
    });
  }

  if (amount <= 0) {
    return res.status(400).json({
      success: false,
      error: 'Amount must be greater than zero'
    });
  }

  // Avoid floating point issues - round to 2 decimal places
  const transferAmount = Math.round(amount * 100) / 100;

  if (fromAccountId === toAccountId) {
    return res.status(400).json({
      success: false,
      error: 'Cannot transfer to the same account'
    });
  }

  const session = await mongoose.startSession();

  try {
    session.startTransaction({
      readConcern: { level: 'snapshot' },
      writeConcern: { w: 'majority' }
    });

    // Find sender account and validate balance
    const fromAccount = await Account.findOne({ userId: fromAccountId }).session(session);
    if (!fromAccount) {
      await session.abortTransaction();
      session.endSession();
      return res.status(404).json({
        success: false,
        error: `Sender account not found: ${fromAccountId}`
      });
    }

    if (fromAccount.balance < transferAmount) {
      await session.abortTransaction();
      session.endSession();
      return res.status(400).json({
        success: false,
        error: 'Insufficient balance',
        currentBalance: fromAccount.balance,
        requestedAmount: transferAmount
      });
    }

    // Find receiver account
    const toAccount = await Account.findOne({ userId: toAccountId }).session(session);
    if (!toAccount) {
      await session.abortTransaction();
      session.endSession();
      return res.status(404).json({
        success: false,
        error: `Receiver account not found: ${toAccountId}`
      });
    }

    // Debit sender
    const debitResult = await Account.updateOne(
      { userId: fromAccountId, balance: { $gte: transferAmount } },
      {
        $inc: { balance: -transferAmount },
        $set: { updatedAt: new Date() }
      }
    ).session(session);

    if (debitResult.modifiedCount !== 1) {
      await session.abortTransaction();
      session.endSession();
      return res.status(400).json({
        success: false,
        error: 'Failed to debit sender account. Possible race condition on balance.'
      });
    }

    // Credit receiver
    const creditResult = await Account.updateOne(
      { userId: toAccountId },
      {
        $inc: { balance: transferAmount },
        $set: { updatedAt: new Date() }
      }
    ).session(session);

    if (creditResult.modifiedCount !== 1) {
      await session.abortTransaction();
      session.endSession();
      return res.status(500).json({
        success: false,
        error: 'Failed to credit receiver account'
      });
    }

    // Create transfer record
    const transfer = new Transfer({
      fromAccountId,
      toAccountId,
      amount: transferAmount,
      status: 'completed'
    });
    await transfer.save({ session });

    // Commit transaction
    await session.commitTransaction();
    session.endSession();

    // Fetch updated balances
    const updatedFromAccount = await Account.findOne({ userId: fromAccountId });
    const updatedToAccount = await Account.findOne({ userId: toAccountId });

    return res.status(200).json({
      success: true,
      message: 'Transfer completed successfully',
      data: {
        transferId: transfer._id,
        fromAccount: {
          userId: fromAccountId,
          newBalance: updatedFromAccount.balance
        },
        toAccount: {
          userId: toAccountId,
          newBalance: updatedToAccount.balance
        },
        amount: transferAmount,
        timestamp: transfer.createdAt
      }
    });
  } catch (error) {
    await session.abortTransaction();
    session.endSession();

    console.error('Transfer error:', error);

    return res.status(500).json({
      success: false,
      error: 'An unexpected error occurred during the transfer',
      details: process.env.NODE_ENV === 'development' ? error.message : undefined
    });
  }
});

// MongoDB connection and server start
const MONGO_URI = process.env.MONGO_URI || 'mongodb://localhost:27017/transfers_db';
const PORT = process.env.PORT || 3000;

mongoose
  .connect(MONGO_URI)
  .then(() => {
    console.log('Connected to MongoDB');
    app.listen(PORT, () => {
      console.log(`Server running on port ${PORT}`);
    });
  })
  .catch((err) => {
    console.error('MongoDB connection error:', err);
    process.exit(1);
  });

module.exports = { app, Account, Transfer };
