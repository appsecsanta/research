/*
================================================================================
FILE: /.env
================================================================================
*/

PORT=3000
MONGO_URI=mongodb://localhost:27017/otp_app

# Twilio Credentials - Replace with your actual credentials
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=+15017122661

/*
================================================================================
FILE: /package.json
================================================================================
*/

{
  "name": "express-otp-service",
  "version": "1.0.0",
  "description": "An Express service for sending and verifying OTPs.",
  "main": "server.js",
  "scripts": {
    "start": "node server.js",
    "dev": "nodemon server.js"
  },
  "keywords": [
    "express",
    "otp",
    "twilio",
    "mongodb"
  ],
  "author": "",
  "license": "ISC",
  "dependencies": {
    "dotenv": "^16.3.1",
    "express": "^4.18.2",
    "mongoose": "^7.6.3",
    "twilio": "^4.19.0"
  },
  "devDependencies": {
    "nodemon": "^3.0.1"
  }
}


/*
================================================================================
FILE: /models/user.model.js
================================================================================
*/

const mongoose = require('mongoose');

const UserSchema = new mongoose.Schema({
  phoneNumber: {
    type: String,
    required: true,
    unique: true,
    trim: true,
  },
  otp: {
    type: String,
    default: null,
  },
  otpExpires: {
    type: Date,
    default: null,
  },
  // Add other user fields as needed (e.g., name, email)
}, {
  timestamps: true
});

module.exports = mongoose.model('User', UserSchema);


/*
================================================================================
FILE: /routes/otp.routes.js
================================================================================
*/

const express = require('express');
const twilio = require('twilio');
const User = require('../models/user.model');

const router = express.Router();

const accountSid = process.env.TWILIO_ACCOUNT_SID;
const authToken = process.env.TWILIO_AUTH_TOKEN;
const twilioPhoneNumber = process.env.TWILIO_PHONE_NUMBER;

if (!accountSid || !authToken || !twilioPhoneNumber) {
  console.error('Twilio environment variables are not set.');
  // In a real app, you might want to prevent the app from starting.
}

const twilioClient = twilio(accountSid, authToken);
const OTP_EXPIRATION_MINUTES = 5;

/**
 * @route   POST /api/send-otp
 * @desc    Generate and send OTP to a user's phone
 * @body    { userId: string }
 */
router.post('/send-otp', async (req, res) => {
  const { userId } = req.body;

  if (!userId) {
    return res.status(400).json({ success: false, message: 'User ID is required.' });
  }

  try {
    const user = await User.findById(userId);
    if (!user) {
      return res.status(404).json({ success: false, message: 'User not found.' });
    }

    const otp = Math.floor(100000 + Math.random() * 900000).toString();
    const otpExpires = new Date(Date.now() + OTP_EXPIRATION_MINUTES * 60 * 1000);

    user.otp = otp;
    user.otpExpires = otpExpires;
    await user.save();

    await twilioClient.messages.create({
      body: `Your verification code is: ${otp}`,
      from: twilioPhoneNumber,
      to: user.phoneNumber,
    });

    return res.status(200).json({ success: true, message: 'OTP sent successfully.' });
  } catch (error) {
    console.error('Error in /send-otp:', error);
    return res.status(500).json({ success: false, message: 'Internal server error.' });
  }
});

/**
 * @route   POST /api/verify-otp
 * @desc    Verify the OTP provided by the user
 * @body    { userId: string, otp: string }
 */
router.post('/verify-otp', async (req, res) => {
  const { userId, otp } = req.body;

  if (!userId || !otp) {
    return res.status(400).json({ success: false, message: 'User ID and OTP are required.' });
  }

  try {
    const user = await User.findOne({
      _id: userId,
      otp: otp,
      otpExpires: { $gt: Date.now() },
    });

    if (!user) {
      return res.status(400).json({ success: false, message: 'Invalid or expired OTP.' });
    }

    user.otp = null;
    user.otpExpires = null;
    await user.save();

    return res.status(200).json({ success: true, message: 'OTP verified successfully.' });
  } catch (error) {
    console.error('Error in /verify-otp:', error);
    return res.status(500).json({ success: false, message: 'Internal server error.' });
  }
});

module.exports = router;


/*
================================================================================
FILE: /server.js
================================================================================
*/

require('dotenv').config();
const express = require('express');
const mongoose = require('mongoose');
const otpRoutes = require('./routes/otp.routes');

const app = express();
const PORT = process.env.PORT || 3000;
const MONGO_URI = process.env.MONGO_URI;

// Middleware
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// API Routes
app.use('/api', otpRoutes);

// Global Error Handler
app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(500).json({ success: false, message: 'An unexpected error occurred.' });
});

const startServer = async () => {
  try {
    await mongoose.connect(MONGO_URI);
    console.log('MongoDB connected successfully.');

    app.listen(PORT, () => {
      console.log(`Server is running on http://localhost:${PORT}`);
      // Optional: Seed a user for easy testing
      seedTestUser();
    });
  } catch (err) {
    console.error('Failed to connect to MongoDB:', err);
    process.exit(1);
  }
};

const seedTestUser = async () => {
  const User = require('./models/user.model');
  const testPhoneNumber = '+15558675309'; // Use a real, Twilio-verified number for testing
  try {
    const existingUser = await User.findOne({ phoneNumber: testPhoneNumber });
    if (!existingUser) {
      const newUser = new User({ phoneNumber: testPhoneNumber });
      const savedUser = await newUser.save();
      console.log(`Test user seeded. Use this ID for API calls: ${savedUser._id}`);
    } else {
      console.log(`Test user already exists. Use this ID for API calls: ${existingUser._id}`);
    }
  } catch (error) {
    console.error('Error seeding test user:', error.message);
  }
};

startServer();
