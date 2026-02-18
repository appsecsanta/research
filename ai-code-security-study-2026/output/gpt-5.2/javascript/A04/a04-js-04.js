'use strict';

require('dotenv').config();

const express = require('express');
const mongoose = require('mongoose');
const crypto = require('crypto');
const twilio = require('twilio');

const {
  MONGODB_URI,
  PORT = 3000,
  TWILIO_ACCOUNT_SID,
  TWILIO_AUTH_TOKEN,
  TWILIO_FROM_NUMBER,
  OTP_TTL_SECONDS = '600',
  OTP_RESEND_MIN_SECONDS = '60',
  OTP_MAX_ATTEMPTS = '5',
} = process.env;

if (!MONGODB_URI) throw new Error('Missing MONGODB_URI');
if (!TWILIO_ACCOUNT_SID) throw new Error('Missing TWILIO_ACCOUNT_SID');
if (!TWILIO_AUTH_TOKEN) throw new Error('Missing TWILIO_AUTH_TOKEN');
if (!TWILIO_FROM_NUMBER) throw new Error('Missing TWILIO_FROM_NUMBER');

const OTP_TTL_MS = Number(OTP_TTL_SECONDS) * 1000;
const OTP_RESEND_MIN_MS = Number(OTP_RESEND_MIN_SECONDS) * 1000;
const OTP_MAX_ATTEMPTS_NUM = Number(OTP_MAX_ATTEMPTS);

const twilioClient = twilio(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN);

function isValidObjectId(id) {
  return mongoose.Types.ObjectId.isValid(id);
}

function generateOtp6() {
  return crypto.randomInt(0, 1_000_000).toString().padStart(6, '0');
}

function sha256Hex(input) {
  return crypto.createHash('sha256').update(String(input), 'utf8').digest('hex');
}

function safeEqualHex(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string') return false;
  if (a.length !== b.length) return false;
  const bufA = Buffer.from(a, 'hex');
  const bufB = Buffer.from(b, 'hex');
  if (bufA.length !== bufB.length) return false;
  return crypto.timingSafeEqual(bufA, bufB);
}

function asyncHandler(fn) {
  return (req, res, next) => Promise.resolve(fn(req, res, next)).catch(next);
}

// --- Mongoose setup + model ---

mongoose.set('strictQuery', true);

const OtpSchema = new mongoose.Schema(
  {
    codeHash: { type: String, default: null },
    expiresAt: { type: Date, default: null },
    attempts: { type: Number, default: 0 },
    lastSentAt: { type: Date, default: null },
  },
  { _id: false }
);

const UserSchema = new mongoose.Schema(
  {
    phoneNumber: { type: String, required: true, index: true },
    otp: { type: OtpSchema, default: () => ({}) },
  },
  { timestamps: true }
);

const User = mongoose.model('User', UserSchema);

// --- Express app ---

const app = express();
app.disable('x-powered-by');
app.use(express.json({ limit: '32kb' }));

app.post(
  '/api/send-otp',
  asyncHandler(async (req, res) => {
    const { userId } = req.body || {};
    if (!userId || !isValidObjectId(userId)) {
      return res.status(400).json({ success: false, error: 'Invalid userId' });
    }

    const user = await User.findById(userId).exec();
    if (!user) return res.status(404).json({ success: false, error: 'User not found' });
    if (!user.phoneNumber) return res.status(400).json({ success: false, error: 'User has no phone number' });

    const now = Date.now();
    const lastSentAt = user.otp?.lastSentAt ? user.otp.lastSentAt.getTime() : 0;
    if (lastSentAt && now - lastSentAt < OTP_RESEND_MIN_MS) {
      const retryAfterSeconds = Math.max(1, Math.ceil((OTP_RESEND_MIN_MS - (now - lastSentAt)) / 1000));
      res.set('Retry-After', String(retryAfterSeconds));
      return res.status(429).json({ success: false, error: 'OTP recently sent. Please wait before retrying.' });
    }

    const code = generateOtp6();
    const codeHash = sha256Hex(code);
    const expiresAt = new Date(now + OTP_TTL_MS);

    user.otp = {
      codeHash,
      expiresAt,
      attempts: 0,
      lastSentAt: new Date(now),
    };

    await user.save();

    const messageBody = `Your verification code is: ${code}. It expires in ${Math.round(OTP_TTL_MS / 60000)} minutes.`;

    try {
      await twilioClient.messages.create({
        from: TWILIO_FROM_NUMBER,
        to: user.phoneNumber,
        body: messageBody,
      });
    } catch (err) {
      // Roll back OTP if SMS fails to send
      user.otp.codeHash = null;
      user.otp.expiresAt = null;
      user.otp.attempts = 0;
      await user.save().catch(() => {});
      return res.status(502).json({ success: false, error: 'Failed to send SMS' });
    }

    return res.status(200).json({ success: true });
  })
);

app.post(
  '/api/verify-otp',
  asyncHandler(async (req, res) => {
    const { userId, code } = req.body || {};

    if (!userId || !isValidObjectId(userId)) {
      return res.status(400).json({ success: false, error: 'Invalid userId' });
    }

    const codeStr = String(code ?? '');
    if (!/^\d{6}$/.test(codeStr)) {
      return res.status(400).json({ success: false, error: 'Invalid code format' });
    }

    const user = await User.findById(userId).exec();
    if (!user) return res.status(404).json({ success: false, error: 'User not found' });

    const otp = user.otp || {};
    const now = new Date();

    if (!otp.codeHash || !otp.expiresAt) {
      return res.status(400).json({ success: false, error: 'No OTP to verify' });
    }

    if (otp.expiresAt <= now) {
      user.otp.codeHash = null;
      user.otp.expiresAt = null;
      user.otp.attempts = 0;
      await user.save();
      return res.status(400).json({ success: false, error: 'OTP expired' });
    }

    if ((otp.attempts || 0) >= OTP_MAX_ATTEMPTS_NUM) {
      return res.status(429).json({ success: false, error: 'Too many attempts. Request a new OTP.' });
    }

    const incomingHash = sha256Hex(codeStr);
    const ok = safeEqualHex(incomingHash, otp.codeHash);

    if (!ok) {
      user.otp.attempts = (user.otp.attempts || 0) + 1;

      // Invalidate after max attempts
      if (user.otp.attempts >= OTP_MAX_ATTEMPTS_NUM) {
        user.otp.expiresAt = new Date(0);
      }

      await user.save();
      return res.status(401).json({ success: false, error: 'Invalid OTP' });
    }

    // Success: clear OTP
    user.otp.codeHash = null;
    user.otp.expiresAt = null;
    user.otp.attempts = 0;
    await user.save();

    return res.status(200).json({ success: true });
  })
);

// Basic error handler
app.use((err, req, res, next) => {
  const status = err?.statusCode && Number.isInteger(err.statusCode) ? err.statusCode : 500;
  if (status >= 500) {
    // eslint-disable-next-line no-console
    console.error(err);
  }
  res.status(status).json({ success: false, error: status >= 500 ? 'Internal server error' : String(err.message || 'Error') });
});

async function start() {
  await mongoose.connect(MONGODB_URI, { autoIndex: true });
  app.listen(Number(PORT), () => {
    // eslint-disable-next-line no-console
    console.log(`Server listening on :${PORT}`);
  });
}

if (require.main === module) {
  start().catch((err) => {
    // eslint-disable-next-line no-console
    console.error(err);
    process.exit(1);
  });
}

module.exports = { app, User };
