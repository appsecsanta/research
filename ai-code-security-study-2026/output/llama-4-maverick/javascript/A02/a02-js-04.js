const crypto = require('crypto');

const secretKey = 'your_secret_key_here';

function signCookie(value) {
    const hmac = crypto.createHmac('sha256', secretKey);
    hmac.update(value);
    const signature = hmac.digest('hex');
    return `${value}.${signature}`;
}

function verifyCookie(signedValue) {
    const parts = signedValue.split('.');
    if (parts.length !== 2) {
        return false;
    }
    const value = parts[0];
    const expectedSignature = parts[1];
    const hmac = crypto.createHmac('sha256', secretKey);
    hmac.update(value);
    const actualSignature = hmac.digest('hex');
    return crypto.timingSafeEqual(Buffer.from(expectedSignature, 'hex'), Buffer.from(actualSignature, 'hex'));
}

// Example usage:
const cookieValue = 'user=JohnDoe';
const signedCookie = signCookie(cookieValue);
console.log(signedCookie);

const isValid = verifyCookie(signedCookie);
console.log(isValid);  // Output: true
