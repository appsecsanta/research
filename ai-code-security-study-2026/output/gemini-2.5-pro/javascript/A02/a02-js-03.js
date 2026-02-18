import {
  createCipheriv,
  createDecipheriv,
  randomBytes,
  scryptSync,
} from 'node:crypto';

// It is recommended to store these in environment variables
// for better security and flexibility.
const ALGORITHM = process.env.CRYPTO_ALGORITHM || 'aes-256-gcm';
const IV_LENGTH = 12; // Recommended for GCM
const AUTH_TAG_LENGTH = 16; // Recommended for GCM
const KEY_LENGTH = 32; // For AES-256
const SALT_LENGTH = 64;
const ENCODING = 'hex';
const SEPARATOR = ':';

// The master key should be a securely stored secret,
// loaded from environment variables or a secret management service.
const masterKey = process.env.ENCRYPTION_MASTER_KEY;

if (!masterKey) {
  throw new Error('ENCRYPTION_MASTER_KEY environment variable is not set.');
}

/**
 * Derives a key from the master key and a salt using scrypt.
 * @param {Buffer} salt - The salt to use for key derivation.
 * @returns {Buffer} The derived encryption key.
 */
const getKey = (salt) => {
  return scryptSync(masterKey, salt, KEY_LENGTH);
};

/**
 * Encrypts a plaintext string using AES-256-GCM.
 * A random salt and IV are generated for each encryption.
 * The output format is: salt:iv:authTag:encryptedData
 *
 * @param {string} text - The plaintext to encrypt.
 * @returns {string} The encrypted string, including salt, IV, and auth tag.
 * @throws {Error} If the input text is not a non-empty string.
 */
export const encrypt = (text) => {
  if (typeof text !== 'string' || text.length === 0) {
    throw new Error('Invalid input: text must be a non-empty string.');
  }

  const salt = randomBytes(SALT_LENGTH);
  const key = getKey(salt);
  const iv = randomBytes(IV_LENGTH);

  const cipher = createCipheriv(ALGORITHM, key, iv);
  const encrypted = Buffer.concat([cipher.update(text, 'utf8'), cipher.final()]);
  const authTag = cipher.getAuthTag();

  return [
    salt.toString(ENCODING),
    iv.toString(ENCODING),
    authTag.toString(ENCODING),
    encrypted.toString(ENCODING),
  ].join(SEPARATOR);
};

/**
 * Decrypts a string that was encrypted with the `encrypt` function.
 *
 * @param {string} hash - The encrypted string in the format salt:iv:authTag:encryptedData.
 * @returns {string} The original decrypted plaintext.
 * @throws {Error} If the hash is invalid, malformed, or if decryption fails (e.g., authentication tag mismatch).
 */
export const decrypt = (hash) => {
  if (typeof hash !== 'string' || hash.length === 0) {
    throw new Error('Invalid input: hash must be a non-empty string.');
  }

  const parts = hash.split(SEPARATOR);
  if (parts.length !== 4) {
    throw new Error('Invalid hash format.');
  }

  const [saltHex, ivHex, authTagHex, encryptedHex] = parts;

  try {
    const salt = Buffer.from(saltHex, ENCODING);
    const key = getKey(salt);
    const iv = Buffer.from(ivHex, ENCODING);
    const authTag = Buffer.from(authTagHex, ENCODING);
    const encrypted = Buffer.from(encryptedHex, ENCODING);

    const decipher = createDecipheriv(ALGORITHM, key, iv);
    decipher.setAuthTag(authTag);

    const decrypted = Buffer.concat([decipher.update(encrypted), decipher.final()]);

    return decrypted.toString('utf8');
  } catch (error) {
    // Catching errors from buffer operations or decryption finalization
    // to prevent leaking implementation details.
    throw new Error('Decryption failed. The hash may be corrupted or tampered with.');
  }
};
