'use strict';

const crypto = require('crypto');

const VERSION = 'v1';
const ALGORITHM = 'aes-256-gcm';
const IV_LENGTH = 12; // 96-bit nonce recommended for GCM
const SALT_LENGTH = 16;
const TAG_LENGTH = 16;
const KEY_LENGTH = 32;
const SCRYPT_N = 1 << 15;
const SCRYPT_R = 8;
const SCRYPT_P = 1;

function b64urlEncode(buf) {
  return Buffer.from(buf)
    .toString('base64')
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/g, '');
}

function b64urlDecode(str) {
  if (typeof str !== 'string') throw new TypeError('Expected a string');
  const s = str.replace(/-/g, '+').replace(/_/g, '/');
  const pad = s.length % 4 === 0 ? '' : '='.repeat(4 - (s.length % 4));
  return Buffer.from(s + pad, 'base64');
}

function normalizeSecret(secret) {
  if (Buffer.isBuffer(secret)) return { type: 'key', value: secret };
  if (typeof secret !== 'string' || secret.length === 0) {
    throw new TypeError('Secret must be a non-empty string or Buffer');
  }
  return { type: 'string', value: secret };
}

function deriveKey(secret, salt) {
  const norm = normalizeSecret(secret);

  if (norm.type === 'key') {
    if (norm.value.length !== KEY_LENGTH) {
      throw new Error(`Key buffer must be exactly ${KEY_LENGTH} bytes`);
    }
    return norm.value;
  }

  const s = norm.value.trim();

  // Allow explicit key formats for operational convenience
  if (s.startsWith('base64:')) {
    const key = Buffer.from(s.slice('base64:'.length), 'base64');
    if (key.length !== KEY_LENGTH) throw new Error(`base64 key must decode to ${KEY_LENGTH} bytes`);
    return key;
  }

  if (s.startsWith('hex:')) {
    const key = Buffer.from(s.slice('hex:'.length), 'hex');
    if (key.length !== KEY_LENGTH) throw new Error(`hex key must decode to ${KEY_LENGTH} bytes`);
    return key;
  }

  // If the provided string looks like a raw 32-byte key, accept it as utf8 bytes.
  // Otherwise, treat it as a passphrase and derive using scrypt (recommended).
  const utf8Bytes = Buffer.from(s, 'utf8');
  if (utf8Bytes.length === KEY_LENGTH) return utf8Bytes;

  return crypto.scryptSync(s, salt, KEY_LENGTH, { N: SCRYPT_N, r: SCRYPT_R, p: SCRYPT_P });
}

function getDefaultSecret() {
  const secret = process.env.DATA_ENCRYPTION_KEY || process.env.ENCRYPTION_KEY || process.env.CRYPTO_SECRET;
  if (!secret) {
    throw new Error(
      'Missing encryption secret. Set DATA_ENCRYPTION_KEY (or provide secret explicitly to encrypt/decrypt).'
    );
  }
  return secret;
}

/**
 * Encrypts a string into a compact token.
 * Format: v1.<salt>.<iv>.<tag>.<ciphertext> (all base64url)
 *
 * @param {string|Buffer} plaintext
 * @param {string|Buffer} [secret]
 * @param {{ aad?: string|Buffer }} [options]
 * @returns {string}
 */
function encrypt(plaintext, secret = getDefaultSecret(), options = {}) {
  if (plaintext === null || plaintext === undefined) {
    throw new TypeError('Plaintext must not be null or undefined');
  }

  const salt = crypto.randomBytes(SALT_LENGTH);
  const iv = crypto.randomBytes(IV_LENGTH);
  const key = deriveKey(secret, salt);

  const cipher = crypto.createCipheriv(ALGORITHM, key, iv);

  if (options.aad !== undefined) {
    const aad = Buffer.isBuffer(options.aad) ? options.aad : Buffer.from(String(options.aad), 'utf8');
    cipher.setAAD(aad);
  }

  const input = Buffer.isBuffer(plaintext) ? plaintext : Buffer.from(String(plaintext), 'utf8');
  const ciphertext = Buffer.concat([cipher.update(input), cipher.final()]);
  const tag = cipher.getAuthTag();
  if (tag.length !== TAG_LENGTH) throw new Error('Unexpected auth tag length');

  return [
    VERSION,
    b64urlEncode(salt),
    b64urlEncode(iv),
    b64urlEncode(tag),
    b64urlEncode(ciphertext),
  ].join('.');
}

/**
 * Decrypts a token produced by encrypt() back into a utf8 string.
 *
 * @param {string} token
 * @param {string|Buffer} [secret]
 * @param {{ aad?: string|Buffer, asBuffer?: boolean }} [options]
 * @returns {string|Buffer}
 */
function decrypt(token, secret = getDefaultSecret(), options = {}) {
  if (typeof token !== 'string' || token.length === 0) {
    throw new TypeError('Token must be a non-empty string');
  }

  const parts = token.split('.');
  if (parts.length !== 5) throw new Error('Invalid token format');

  const [version, saltB64, ivB64, tagB64, ciphertextB64] = parts;
  if (version !== VERSION) throw new Error(`Unsupported token version: ${version}`);

  const salt = b64urlDecode(saltB64);
  const iv = b64urlDecode(ivB64);
  const tag = b64urlDecode(tagB64);
  const ciphertext = b64urlDecode(ciphertextB64);

  if (salt.length !== SALT_LENGTH) throw new Error('Invalid salt length');
  if (iv.length !== IV_LENGTH) throw new Error('Invalid IV length');
  if (tag.length !== TAG_LENGTH) throw new Error('Invalid auth tag length');

  const key = deriveKey(secret, salt);

  const decipher = crypto.createDecipheriv(ALGORITHM, key, iv);
  decipher.setAuthTag(tag);

  if (options.aad !== undefined) {
    const aad = Buffer.isBuffer(options.aad) ? options.aad : Buffer.from(String(options.aad), 'utf8');
    decipher.setAAD(aad);
  }

  const plaintext = Buffer.concat([decipher.update(ciphertext), decipher.final()]);
  return options.asBuffer ? plaintext : plaintext.toString('utf8');
}

module.exports = {
  encrypt,
  decrypt,
};
