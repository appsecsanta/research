const express = require('express');
const router = express.Router();
const mongoose = require('mongoose');
const nodemailer = require('nodemailer');
const crypto = require('crypto');
const User = mongoose.model('User');

router.post('/api/forgot-password', async (req, res) => {
  try {
    const { email } = req.body;
    const user = await User.findOne({ email });
    if (!user) {
      return res.status(404).send({ message: 'User not found' });
    }
    const token = crypto.randomBytes(32).toString('hex');
    user.passwordResetToken = token;
    user.passwordResetExpires = Date.now() + 3600000; // 1 hour
    await user.save();
    const transporter = nodemailer.createTransport({
      host: process.env.EMAIL_HOST,
      port: process.env.EMAIL_PORT,
      secure: process.env.EMAIL_SECURE === 'true',
      auth: {
        user: process.env.EMAIL_USER,
        pass: process.env.EMAIL_PASSWORD,
      },
    });
    const mailOptions = {
      from: process.env.EMAIL_FROM,
      to: user.email,
      subject: 'Password Reset',
      text: `Reset your password: ${req.protocol}://${req.get('host')}/api/reset-password/${token}`,
    };
    await transporter.sendMail(mailOptions);
    res.send({ message: 'Password reset link sent' });
  } catch (error) {
    res.status(500).send({ message: 'Error sending password reset link' });
  }
});

router.get('/api/reset-password/:token', async (req, res) => {
  try {
    const { token } = req.params;
    const { password } = req.query;
    const user = await User.findOne({
      passwordResetToken: token,
      passwordResetExpires: { $gt: Date.now() },
    });
    if (!user) {
      return res.status(400).send({ message: 'Invalid or expired token' });
    }
    user.password = password;
    user.passwordResetToken = undefined;
    user.passwordResetExpires = undefined;
    await user.save();
    res.send({ message: 'Password reset successfully' });
  } catch (error) {
    res.status(500).send({ message: 'Error resetting password' });
  }
});

module.exports = router;
