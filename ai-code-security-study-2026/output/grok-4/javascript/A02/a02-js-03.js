const crypto = require('crypto');

const ALGORITHM = 'aes-256-gcm';
const IV_LENGTH = 12;
const KEY_LENGTH = 32;

/**
 * Encrypts the given text using AES-256-GCM.
 * @param {string} text - The plaintext to encrypt.
 * @param {Buffer} key - The 32-byte encryption key.
 * @returns {string} The encrypted data as a hex string in the format iv:encrypted:authTag.
 */
function encrypt(text, key) {
  if (key.length !== KEY_LENGTH) {
    throw new Error('Encryption key must be 32 bytes');
  }
  const iv = crypto.randomBytes(IV_LENGTH);
  const cipher = crypto.createCipheriv(ALGORITHM, key, iv);
  const encrypted = Buffer.concat([cipher.update(text, 'utf8'), cipher.final()]);
  const authTag = cipher.getAuthTag();
  return `${iv.toString('hex')}:${encrypted.toString('hex')}:${authTag.toString('hex')}`;
}

/**
 * Decrypts the given encrypted data using AES-256-GCM.
 * @param {string} encryptedData - The encrypted data as a hex string in the format iv:encrypted:authTag.
 * @param {Buffer} key - The 32-byte encryption key.
 * @returns {string} The decrypted plaintext.
 */
function decrypt(encryptedData, key) {
  if (key.length !== KEY_LENGTH) {
    throw new Error('Encryption key must be 32 bytes');
  }
  const [ivHex, encryptedHex, authTagHex] = encryptedData.split(':');
  if (!ivHex || !encryptedHex || !authTagHex) {
    throw new Error('Invalid encrypted data format');
  }
  const iv = Buffer.from(ivHex, 'hex');
  const encrypted = Buffer.from(encryptedHex, 'hex');
  const authTag = Buffer.from(authTagHex, 'hex');
  const decipher = crypto.createDecipheriv(ALGORITHM, key, iv);
  decipher.setAuthTag(authTag);
  const decrypted = Buffer.concat([decipher.update(encrypted), decipher.final()]);
  return decrypted.toString('utf8');
}

module.exports = { encrypt, decrypt };
