const crypto = require('crypto');

/**
 * Signs a value with a secret key using HMAC-SHA256.
 * The signature is base64url encoded to be safe for cookie values.
 *
 * @param {string} value The string value to sign.
 * @param {string} secret The secret key for signing.
 * @returns {string} The signed value in the format "value.signature".
 * @throws {TypeError} If value or secret are not strings.
 */
function sign(value, secret) {
  if (typeof value !== 'string' || typeof secret !== 'string') {
    throw new TypeError('Value and secret must be strings.');
  }

  const hmac = crypto.createHmac('sha256', secret);
  hmac.update(value);
  const signature = hmac.digest('base64url');

  return `${value}.${signature}`;
}

/**
 * Verifies a signed value against a secret key.
 * Uses a constant-time comparison algorithm to prevent timing attacks.
 *
 * @param {string} signedValue The signed value to verify (e.g., from a cookie).
 * @param {string} secret The secret key used for signing.
 * @returns {string|false} The original unsigned value if the signature is valid, otherwise false.
 */
function verify(signedValue, secret) {
  if (typeof signedValue !== 'string' || typeof secret !== 'string') {
    return false;
  }

  const lastDotIndex = signedValue.lastIndexOf('.');
  if (lastDotIndex === -1) {
    return false;
  }

  const value = signedValue.slice(0, lastDotIndex);
  const signature = signedValue.slice(lastDotIndex + 1);

  if (!value || !signature) {
    return false;
  }

  const hmac = crypto.createHmac('sha256', secret);
  hmac.update(value);
  const expectedSignature = hmac.digest('base64url');

  const signatureBuffer = Buffer.from(signature);
  const expectedSignatureBuffer = Buffer.from(expectedSignature);

  if (signatureBuffer.length !== expectedSignatureBuffer.length) {
    return false;
  }

  const areSignaturesEqual = crypto.timingSafeEqual(signatureBuffer, expectedSignatureBuffer);

  return areSignaturesEqual ? value : false;
}
