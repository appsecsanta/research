const express = require('express');
const mongoose = require('mongoose');
const twilio = require('twilio');
const crypto = require('crypto');

// Configuration
const config = {
  mongoUri: process.env.MONGO_URI || 'mongodb://localhost:27017/otp-service',
  twilioAccountSid: process.env.TWILIO_ACCOUNT_SID,
  twilioAuthToken: process.env.TWILIO_AUTH_TOKEN,
  twilioPhoneNumber: process.env.TWILIO_PHONE_NUMBER,
  otpExpiryMinutes: parseInt(process.env.OTP_EXPIRY_MINUTES, 10) || 5,
  maxAttempts: parseInt(process.env.OTP_MAX_ATTEMPTS, 10) || 3,
  port: parseInt(process.env.PORT, 10) || 3000,
};

// MongoDB Schemas
const userSchema = new mongoose.Schema({
  phone: {
    type: String,
    required: true,
    unique: true,
    trim: true,
  },
  name: {
    type: String,
    trim: true,
  },
  verified: {
    type: Boolean,
    default: false,
  },
  createdAt: {
    type: Date,
    default: Date.now,
  },
});

const otpSchema = new mongoose.Schema({
  userId: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'User',
    required: true,
    index: true,
  },
  code: {
    type: String,
    required: true,
  },
  attempts: {
    type: Number,
    default: 0,
  },
  maxAttempts: {
    type: Number,
    default: 3,
  },
  expiresAt: {
    type: Date,
    required: true,
    index: { expires: 0 },
  },
  verified: {
    type: Boolean,
    default: false,
  },
  createdAt: {
    type: Date,
    default: Date.now,
  },
});

const User = mongoose.model('User', userSchema);
const OTP = mongoose.model('OTP', otpSchema);

// Twilio client
const twilioClient = twilio(config.twilioAccountSid, config.twilioAuthToken);

// Helper: generate a cryptographically secure 6-digit OTP
function generateOTP() {
  const buffer = crypto.randomBytes(4);
  const num = buffer.readUInt32BE(0) % 1000000;
  return num.toString().padStart(6, '0');
}

// Express app
const app = express();
app.use(express.json());

// POST /api/send-otp
app.post('/api/send-otp', async (req, res) => {
  try {
    const { userId } = req.body;

    if (!userId) {
      return res.status(400).json({
        success: false,
        message: 'userId is required.',
      });
    }

    if (!mongoose.Types.ObjectId.isValid(userId)) {
      return res.status(400).json({
        success: false,
        message: 'Invalid userId format.',
      });
    }

    const user = await User.findById(userId);
    if (!user) {
      return res.status(404).json({
        success: false,
        message: 'User not found.',
      });
    }

    // Rate limiting: check if there's a recent unexpired OTP
    const recentOtp = await OTP.findOne({
      userId: user._id,
      verified: false,
      expiresAt: { $gt: new Date() },
      createdAt: { $gt: new Date(Date.now() - 60 * 1000) }, // within last 60 seconds
    });

    if (recentOtp) {
      return res.status(429).json({
        success: false,
        message: 'An OTP was recently sent. Please wait before requesting a new one.',
      });
    }

    // Invalidate any existing unverified OTPs for this user
    await OTP.updateMany(
      { userId: user._id, verified: false },
      { $set: { expiresAt: new Date() } }
    );

    // Generate OTP
    const code = generateOTP();
    const expiresAt = new Date(Date.now() + config.otpExpiryMinutes * 60 * 1000);

    // Store OTP in MongoDB
    const otpRecord = await OTP.create({
      userId: user._id,
      code,
      maxAttempts: config.maxAttempts,
      expiresAt,
    });

    // Send OTP via Twilio SMS
    await twilioClient.messages.create({
      body: `Your verification code is: ${code}. It expires in ${config.otpExpiryMinutes} minutes.`,
      from: config.twilioPhoneNumber,
      to: user.phone,
    });

    return res.status(200).json({
      success: true,
      message: 'OTP sent successfully.',
      data: {
        otpId: otpRecord._id,
        expiresAt: otpRecord.expiresAt,
      },
    });
  } catch (error) {
    console.error('Error in /api/send-otp:', error);

    if (error.code && error.message && error.status) {
      // Twilio error
      return res.status(502).json({
        success: false,
        message: 'Failed to send SMS. Please try again later.',
      });
    }

    return res.status(500).json({
      success: false,
      message: 'Internal server error.',
    });
  }
});

// POST /api/verify-otp
app.post('/api/verify-otp', async (req, res) => {
  try {
    const { userId, code } = req.body;

    if (!userId || !code) {
      return res.status(400).json({
        success: false,
        message: 'userId and code are required.',
      });
    }

    if (!mongoose.Types.ObjectId.isValid(userId)) {
      return res.status(400).json({
        success: false,
        message: 'Invalid userId format.',
      });
    }

    // Validate code format
    const codeStr = String(code).trim();
    if (!/^\d{6}$/.test(codeStr)) {
      return res.status(400).json({
        success: false,
        message: 'OTP must be a 6-digit numeric code.',
      });
    }

    const user = await User.findById(userId);
    if (!user) {
      return res.status(404).json({
        success: false,
        message: 'User not found.',
      });
    }

    // Find the most recent unverified, unexpired OTP for this user
    const otpRecord = await OTP.findOne({
      userId: user._id,
      verified: false,
      expiresAt: { $gt: new Date() },
    }).sort({ createdAt: -1 });

    if (!otpRecord) {
      return res.status(400).json({
        success: false,
        message: 'No valid OTP found. Please request a new one.',
      });
    }

    // Check max attempts
    if (otpRecord.attempts >= otpRecord.maxAttempts) {
      // Expire the OTP
      otpRecord.expiresAt = new Date();
      await otpRecord.save();

      return res.status(400).json({
        success: false,
        message: 'Maximum verification attempts exceeded. Please request a new OTP.',
      });
    }

    // Increment attempts
    otpRecord.attempts += 1;

    // Use timing-safe comparison to prevent timing attacks
    const codeBuffer = Buffer.from(codeStr);
    const storedBuffer = Buffer.from(otpRecord.code);

    const isMatch =
      codeBuffer.length === storedBuffer.length &&
      crypto.timingSafeEqual(codeBuffer, storedBuffer);

    if (!isMatch) {
      await otpRecord.save();

      const remainingAttempts = otpRecord.maxAttempts - otpRecord.attempts;

      return res.status(400).json({
        success: false,
        message: 'Invalid OTP code.',
        data: {
          remainingAttempts,
        },
      });
    }

    // Mark OTP as verified
    otpRecord.verified = true;
    await otpRecord.save();

    // Mark user as verified
    user.verified = true;
    await user.save();

    return res.status(200).json({
      success: true,
      message: 'OTP verified successfully.',
    });
  } catch (error) {
    console.error('Error in /api/verify-otp:', error);
    return res.status(500).json({
      success: false,
      message: 'Internal server error.',
    });
  }
});

// Health check
app.get('/health', (req, res) => {
  res.status(200).json({ status: 'ok' });
});

// Connect to MongoDB and start server
async function start() {
  try {
    await mongoose.connect(config.mongoUri);
    console.log('Connected to MongoDB');

    app.listen(config.port, () => {
      console.log(`Server running on port ${config.port}`);
    });
  } catch (error) {
    console.error('Failed to start server:', error);
    process.exit(1);
  }
}

start();

module.exports = app;
