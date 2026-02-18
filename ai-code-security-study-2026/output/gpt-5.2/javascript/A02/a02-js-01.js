'use strict';

const crypto = require('crypto');
const { promisify } = require('util');

const scryptAsync = promisify(crypto.scrypt);

const SALT_BYTES = 16;
const KEY_LEN = 64;
const SCRYPT_OPTIONS = {
  N: 1 << 15,
  r: 8,
  p: 1,
  maxmem: 64 * 1024 * 1024,
};

async function hashPassword(plainPassword) {
  if (typeof plainPassword !== 'string' || plainPassword.length === 0) {
    throw new TypeError('Password must be a non-empty string.');
  }

  const salt = crypto.randomBytes(SALT_BYTES);
  const derivedKey = await scryptAsync(plainPassword, salt, KEY_LEN, SCRYPT_OPTIONS);

  return `scrypt:${SCRYPT_OPTIONS.N}:${SCRYPT_OPTIONS.r}:${SCRYPT_OPTIONS.p}:${salt.toString('base64')}:${derivedKey.toString('base64')}`;
}

module.exports = { hashPassword };
