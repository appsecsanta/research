// otp.route.js
const express = require('express');
const { sendOtp, verifyOtp } = require('./otp.controller');
const User = require('./user.model');

const router = express.Router();

router.post('/send-otp', async (req, res) => {
  try {
    const { userId } = req.body;
    const user = await User.findById(userId);
    if (!user) {
      return res.status(404).json({ error: 'User not found' });
    }
    await sendOtp(userId, user.phoneNumber);
    res.json({ message: 'OTP sent successfully' });
  } catch (error) {
    res.status(500).json({ error: 'Failed to send OTP' });
  }
});

router.post('/verify-otp', async (req, res) => {
  try {
    const { userId, otp } = req.body;
    const isValid = await verifyOtp(userId, otp);
    if (!isValid) {
      return res.status(401).json({ error: 'Invalid OTP' });
    }
    res.json({ message: 'OTP verified successfully' });
  } catch (error) {
    res.status(500).json({ error: 'Failed to verify OTP' });
  }
});

module.exports = router;
