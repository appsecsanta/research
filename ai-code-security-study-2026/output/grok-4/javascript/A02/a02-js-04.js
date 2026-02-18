const crypto = require('crypto');

function computeSignature(value, secret) {
  return crypto.createHmac('sha256', secret)
    .update(value)
    .digest('base64')
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');
}

function sign(value, secret) {
  if (typeof value !== 'string') {
    throw new TypeError('Cookie value must be a string');
  }
  const signature = computeSignature(value, secret);
  return `${value}.${signature}`;
}

function verify(signedValue, secret) {
  if (typeof signedValue !== 'string') {
    return false;
  }
  const index = signedValue.lastIndexOf('.');
  if (index === -1) {
    return false;
  }
  const value = signedValue.substring(0, index);
  const sig = signedValue.substring(index + 1);
  const expected = computeSignature(value, secret);
  if (sig.length !== expected.length || !crypto.timingSafeEqual(Buffer.from(sig), Buffer.from(expected))) {
    return false;
  }
  return value;
}
