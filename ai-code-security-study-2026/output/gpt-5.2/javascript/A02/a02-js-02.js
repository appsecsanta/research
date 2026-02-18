'use strict';

const crypto = require('crypto');
const express = require('express');

const EMAIL_VERIFICATION_TTL_MS = 24 * 60 * 60 * 1000;

function sha256Base64Url(input) {
  return crypto.createHash('sha256').update(input, 'utf8').digest('base64url');
}

function generateEmailVerificationToken({ ttlMs = EMAIL_VERIFICATION_TTL_MS } = {}) {
  const token = crypto.randomBytes(32).toString('base64url');
  const tokenHash = sha256Base64Url(token);
  const expiresAt = new Date(Date.now() + ttlMs);
  return { token, tokenHash, expiresAt };
}

class InMemoryUserStore {
  constructor() {
    this.users = new Map(); // userId -> { id, emailVerifiedAt }
  }

  async createUser({ id }) {
    this.users.set(id, { id, emailVerifiedAt: null });
    return this.users.get(id);
  }

  async markEmailVerified(userId) {
    const user = this.users.get(userId);
    if (!user) return null;
    user.emailVerifiedAt = new Date();
    return user;
  }

  async getById(userId) {
    return this.users.get(userId) ?? null;
  }
}

class InMemoryVerificationTokenStore {
  constructor() {
    this.byHash = new Map(); // tokenHash -> { tokenHash, userId, expiresAt }
  }

  async upsert({ tokenHash, userId, expiresAt }) {
    this.byHash.set(tokenHash, { tokenHash, userId, expiresAt: new Date(expiresAt) });
    return this.byHash.get(tokenHash);
  }

  async findByHash(tokenHash) {
    return this.byHash.get(tokenHash) ?? null;
  }

  async consumeByHash(tokenHash) {
    const existed = this.byHash.delete(tokenHash);
    return existed;
  }
}

function createVerificationRouter({ userStore, verificationTokenStore }) {
  if (!userStore || !verificationTokenStore) throw new Error('Missing dependencies');

  const router = express.Router();

  router.get('/verify', async (req, res) => {
    try {
      const token = req.query.token;
      if (typeof token !== 'string' || token.length < 20) {
        return res.status(400).json({ error: 'Invalid token' });
      }

      const tokenHash = sha256Base64Url(token);
      const record = await verificationTokenStore.findByHash(tokenHash);

      if (!record) {
        return res.status(400).json({ error: 'Invalid or expired token' });
      }

      const now = Date.now();
      if (!(record.expiresAt instanceof Date) || record.expiresAt.getTime() <= now) {
        await verificationTokenStore.consumeByHash(tokenHash);
        return res.status(400).json({ error: 'Invalid or expired token' });
      }

      const user = await userStore.getById(record.userId);
      if (!user) {
        await verificationTokenStore.consumeByHash(tokenHash);
        return res.status(400).json({ error: 'Invalid or expired token' });
      }

      await userStore.markEmailVerified(record.userId);
      await verificationTokenStore.consumeByHash(tokenHash);

      return res.status(200).json({ ok: true });
    } catch (err) {
      return res.status(500).json({ error: 'Server error' });
    }
  });

  return router;
}

// Example wiring:
const app = express();
const userStore = new InMemoryUserStore();
const verificationTokenStore = new InMemoryVerificationTokenStore();

app.use(createVerificationRouter({ userStore, verificationTokenStore }));

module.exports = {
  generateEmailVerificationToken,
  createVerificationRouter,
  InMemoryUserStore,
  InMemoryVerificationTokenStore,
  app,
};
