const express = require('express');
const mongoose = require('mongoose');
const twilio = require('twilio');
const router = express.Router();

const User = mongoose.model('User', new mongoose.Schema({
  userId: String,
  otpCode: String
}));

const client = twilio(process.env.TWILIO_ACCOUNT_SID, process.env.TWILIO_AUTH_TOKEN);

router.post('/api/send-otp', async (req, res) => {
  const { userId, phoneNumber } = req.body;
  const otpCode = Math.floor(100000 + Math.random() * 900000).toString();

  try {
    await User.findOneAndUpdate(
      { userId },
      { otpCode },
      { upsert: true, new: true }
    );

    await client.messages.create({
      body: `Your OTP code is ${otpCode}`,
      from: process.env.TWILIO_PHONE_NUMBER,
      to: phoneNumber
    });

    res.status(200).json({ success: true });
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
});

router.post('/api/verify-otp', async (req, res) => {
  const { userId, otpCode } = req.body;

  try {
    const user = await User.findOne({ userId });

    if (user && user.otpCode === otpCode) {
      res.status(200).json({ success: true });
    } else {
      res.status(400).json({ success: false });
    }
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
});

module.exports = router;
