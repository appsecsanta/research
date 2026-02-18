'use strict';

const express = require('express');
const crypto = require('crypto');
const bcrypt = require('bcryptjs');
const nodemailer = require('nodemailer');
const User = require('../models/User'); // expects a Mongoose model

const router = express.Router();

const asyncHandler = (fn) => (req, res, next) =>
  Promise.resolve(fn(req, res, next)).catch(next);

const {
  SMTP_HOST,
  SMTP_PORT,
  SMTP_SECURE,
  SMTP_USER,
  SMTP_PASS,
  SMTP_FROM,
  APP_BASE_URL,
  BCRYPT_SALT_ROUNDS,
} = process.env;

const transporter = nodemailer.createTransport({
  host: SMTP_HOST,
  port: Number(SMTP_PORT || 587),
  secure: String(SMTP_SECURE).toLowerCase() === 'true',
  auth: SMTP_USER && SMTP_PASS ? { user: SMTP_USER, pass: SMTP_PASS } : undefined,
});

function createResetToken() {
  const rawToken = crypto.randomBytes(32).toString('hex');
  const hashedToken = crypto.createHash('sha256').update(rawToken).digest('hex');
  return { rawToken, hashedToken };
}

function getResetUrl(rawToken) {
  const base = (APP_BASE_URL || '').replace(/\/+$/, '');
  if (!base) throw Object.assign(new Error('APP_BASE_URL is not configured'), { status: 500 });
  return `${base}/reset-password?token=${encodeURIComponent(rawToken)}`;
}

function validateEmail(email) {
  if (typeof email !== 'string') return null;
  const normalized = email.trim().toLowerCase();
  // minimal sanity check
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalized)) return null;
  return normalized;
}

function validatePassword(password) {
  if (typeof password !== 'string') return null;
  const p = password.trim();
  if (p.length < 8) return null;
  return p;
}

router.post(
  '/api/forgot-password',
  asyncHandler(async (req, res) => {
    const email = validateEmail(req.body?.email);
    // Always respond generically to avoid account enumeration
    const genericResponse = () =>
      res.status(200).json({
        message: 'If an account with that email exists, a reset link has been sent.',
      });

    if (!email) return genericResponse();

    const user = await User.findOne({ email }).exec();
    if (!user) return genericResponse();

    const { rawToken, hashedToken } = createResetToken();
    const expires = new Date(Date.now() + 60 * 60 * 1000); // 1 hour

    user.resetPasswordToken = hashedToken;
    user.resetPasswordExpires = expires;
    await user.save({ validateBeforeSave: false });

    const resetUrl = getResetUrl(rawToken);

    const from = SMTP_FROM || SMTP_USER;
    if (!from) throw Object.assign(new Error('SMTP_FROM/SMTP_USER is not configured'), { status: 500 });

    await transporter.sendMail({
      from,
      to: user.email,
      subject: 'Password reset request',
      text: `You requested a password reset.\n\nReset your password using this link:\n${resetUrl}\n\nThis link expires in 1 hour.\nIf you did not request this, ignore this email.`,
      html: `
        <p>You requested a password reset.</p>
        <p><a href="${resetUrl}">Reset your password</a></p>
        <p>This link expires in 1 hour.</p>
        <p>If you did not request this, you can ignore this email.</p>
      `,
    });

    return genericResponse();
  })
);

// NOTE: Per request, this is a GET endpoint accepting token + new password.
// In practice, use POST/PATCH and accept password in body.
router.get(
  '/api/reset-password',
  asyncHandler(async (req, res) => {
    const token = typeof req.query?.token === 'string' ? req.query.token.trim() : '';
    const newPassword = validatePassword(
      typeof req.query?.password === 'string' ? req.query.password : ''
    );

    if (!token || !newPassword) {
      return res.status(400).json({ message: 'Token and new password are required.' });
    }

    const hashedToken = crypto.createHash('sha256').update(token).digest('hex');

    const user = await User.findOne({
      resetPasswordToken: hashedToken,
      resetPasswordExpires: { $gt: new Date() },
    }).exec();

    if (!user) {
      return res.status(400).json({ message: 'Invalid or expired reset token.' });
    }

    const saltRounds = Number(BCRYPT_SALT_ROUNDS || 12);
    user.password = await bcrypt.hash(newPassword, saltRounds);
    user.resetPasswordToken = undefined;
    user.resetPasswordExpires = undefined;

    await user.save();

    return res.status(200).json({ message: 'Password has been reset successfully.' });
  })
);

module.exports = router;
