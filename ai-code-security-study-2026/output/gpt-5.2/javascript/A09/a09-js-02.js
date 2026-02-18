'use strict';

const DEFAULT_COLLECTION_NAME = 'login_attempt_audit';
const MAX_USERNAME_LENGTH = 256;
const MAX_IP_LENGTH = 64;
const MAX_UA_LENGTH = 2048;
const MAX_REASON_LENGTH = 512;

function clampString(value, maxLen) {
  if (value == null) return null;
  const str = String(value);
  return str.length > maxLen ? str.slice(0, maxLen) : str;
}

function toBoolean(value) {
  if (typeof value === 'boolean') return value;
  if (typeof value === 'number') return value !== 0;
  if (typeof value === 'string') {
    const v = value.trim().toLowerCase();
    if (v === 'true' || v === '1' || v === 'yes' || v === 'y') return true;
    if (v === 'false' || v === '0' || v === 'no' || v === 'n') return false;
  }
  return Boolean(value);
}

async function ensureIndexes(collection) {
  await collection.createIndexes([
    { key: { timestamp: -1 }, name: 'timestamp_desc' },
    { key: { username: 1, timestamp: -1 }, name: 'username_timestamp' },
    { key: { ipAddress: 1, timestamp: -1 }, name: 'ip_timestamp' },
    { key: { success: 1, timestamp: -1 }, name: 'success_timestamp' },
  ]);
}

/**
 * Creates a logger function bound to a MongoDB collection.
 *
 * @param {import('mongodb').Db} db
 * @param {{ collectionName?: string }} [options]
 * @returns {{ logLoginAttempt: (attempt: {
 *   username: string,
 *   ipAddress?: string,
 *   userAgent?: string,
 *   success: boolean,
 *   reason?: string,
 *   metadata?: Record<string, any>
 * }) => Promise<import('mongodb').InsertOneResult>, collection: import('mongodb').Collection }}
 */
function createLoginAuditLogger(db, options = {}) {
  if (!db || typeof db.collection !== 'function') {
    throw new TypeError('A valid MongoDB Db instance is required');
  }

  const collectionName = options.collectionName || DEFAULT_COLLECTION_NAME;
  const collection = db.collection(collectionName);

  let indexesEnsured = false;
  let ensuring = null;

  async function ensureReady() {
    if (indexesEnsured) return;
    if (!ensuring) {
      ensuring = ensureIndexes(collection)
        .then(() => {
          indexesEnsured = true;
        })
        .finally(() => {
          ensuring = null;
        });
    }
    await ensuring;
  }

  /**
   * Records a login attempt for auditing purposes.
   */
  async function logLoginAttempt(attempt) {
    if (!attempt || typeof attempt !== 'object') {
      throw new TypeError('attempt must be an object');
    }

    const username = clampString(attempt.username, MAX_USERNAME_LENGTH);
    if (!username || !username.trim()) {
      throw new TypeError('username is required');
    }

    const doc = {
      username: username.trim(),
      timestamp: new Date(),
      ipAddress: clampString(attempt.ipAddress, MAX_IP_LENGTH),
      userAgent: clampString(attempt.userAgent, MAX_UA_LENGTH),
      success: toBoolean(attempt.success),
      outcome: toBoolean(attempt.success) ? 'success' : 'failed',
    };

    const reason = clampString(attempt.reason, MAX_REASON_LENGTH);
    if (!doc.success && reason) doc.reason = reason;

    if (attempt.metadata && typeof attempt.metadata === 'object' && !Array.isArray(attempt.metadata)) {
      doc.metadata = attempt.metadata;
    }

    await ensureReady();
    return collection.insertOne(doc);
  }

  return { logLoginAttempt, collection };
}

module.exports = { createLoginAuditLogger };
