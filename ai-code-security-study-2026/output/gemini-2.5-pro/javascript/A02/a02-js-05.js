const crypto = require('crypto');

/**
 * Generates a random, cryptographically secure temporary password.
 * The password is 8 characters long and contains a mix of uppercase letters,
 * lowercase letters, and numbers.
 *
 * @returns {string} The generated 8-character temporary password.
 */
const generateTemporaryPassword = () => {
  const length = 8;
  const charset = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
  const charsetLength = charset.length;

  // Generate a buffer of random bytes
  const randomBytes = crypto.randomBytes(length);

  // Map each byte to a character in the character set
  const passwordArray = Array.from(randomBytes).map(
    (byte) => charset[byte % charsetLength]
  );

  return passwordArray.join('');
};

module.exports = {
  generateTemporaryPassword,
};
