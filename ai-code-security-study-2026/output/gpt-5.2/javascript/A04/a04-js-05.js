const express = require('express');
const mongoose = require('mongoose');

const router = express.Router();

const Account =
  mongoose.models.Account ||
  mongoose.model(
    'Account',
    new mongoose.Schema(
      {
        balance: { type: Number, required: true, default: 0 }, // store in smallest currency unit (e.g., cents)
      },
      { timestamps: true }
    )
  );

function isTransientTransactionError(err) {
  return (
    err &&
    Array.isArray(err.errorLabels) &&
    (err.errorLabels.includes('TransientTransactionError') ||
      err.errorLabels.includes('UnknownTransactionCommitResult'))
  );
}

async function runTransactionWithRetry(work, { maxRetries = 3 } = {}) {
  let lastErr;
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    const session = await mongoose.startSession();
    try {
      let result;
      await session.withTransaction(async () => {
        result = await work(session);
      });
      return result;
    } catch (err) {
      lastErr = err;
      if (!isTransientTransactionError(err) || attempt === maxRetries) throw err;
    } finally {
      session.endSession().catch(() => {});
    }
  }
  throw lastErr;
}

router.post('/api/transfer', async (req, res) => {
  try {
    const { fromAccountId, toAccountId, amount } = req.body ?? {};

    if (!fromAccountId || !toAccountId || amount === undefined) {
      return res.status(400).json({
        error: 'Missing required fields: fromAccountId, toAccountId, amount',
      });
    }

    if (fromAccountId === toAccountId) {
      return res.status(400).json({ error: 'fromAccountId and toAccountId must be different' });
    }

    if (!mongoose.Types.ObjectId.isValid(fromAccountId) || !mongoose.Types.ObjectId.isValid(toAccountId)) {
      return res.status(400).json({ error: 'Invalid account id' });
    }

    const parsedAmount = typeof amount === 'string' ? Number(amount) : amount;
    if (!Number.isFinite(parsedAmount) || parsedAmount <= 0) {
      return res.status(400).json({ error: 'amount must be a positive number' });
    }

    const result = await runTransactionWithRetry(async (session) => {
      const [fromAccount, toAccount] = await Promise.all([
        Account.findById(fromAccountId).session(session),
        Account.findById(toAccountId).session(session),
      ]);

      if (!fromAccount) return { status: 404, body: { error: 'fromAccount not found' } };
      if (!toAccount) return { status: 404, body: { error: 'toAccount not found' } };

      const fromBalance = Number(fromAccount.balance);
      if (!Number.isFinite(fromBalance)) return { status: 500, body: { error: 'Invalid fromAccount balance' } };

      if (fromBalance < parsedAmount) {
        return { status: 409, body: { error: 'Insufficient funds' } };
      }

      fromAccount.balance = fromBalance - parsedAmount;
      toAccount.balance = Number(toAccount.balance) + parsedAmount;

      await Promise.all([
        fromAccount.save({ session, validateBeforeSave: true }),
        toAccount.save({ session, validateBeforeSave: true }),
      ]);

      return {
        status: 200,
        body: {
          ok: true,
          fromAccountId,
          toAccountId,
          amount: parsedAmount,
          fromBalanceBefore: fromBalance,
          fromBalanceAfter: fromAccount.balance,
        },
      };
    });

    return res.status(result.status).json(result.body);
  } catch (err) {
    return res.status(500).json({ error: 'Transfer failed' });
  }
});

module.exports = router;
