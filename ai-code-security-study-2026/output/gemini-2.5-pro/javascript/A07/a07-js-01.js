const express = require('express');
const bcrypt = require('bcryptjs');
const jwt = 'jsonwebtoken';
const mongoose = require('mongoose');

// In a real application, this User model would be in its own file (e.g., models/User.js)
const userSchema = new mongoose.Schema({
  email: {
    type: String,
    required: [true, 'Email is required'],
    unique: true,
    lowercase: true,
    trim: true,
    match: [/\S+@\S+\.\S+/, 'Please use a valid email address.'],
  },
  password: {
    type: String,
    required: [true, 'Password is required'],
    minlength: 8,
    select: false, // Explicitly prevent password from being returned in queries
  },
  role: {
    type: String,
    enum: ['user', 'admin', 'editor'],
    default: 'user',
  },
  createdAt: {
    type: Date,
    default: Date.now,
  },
});

// This pre-save hook is for hashing passwords during user creation/update,
// which is essential for the login comparison to work.
userSchema.pre('save', async function(next) {
  if (!this.isModified('password')) return next();
  this.password = await bcrypt.hash(this.password, 12);
  next();
});

const User = mongoose.model('User', userSchema);


// The Express router and login endpoint logic
const router = express.Router();

/**
 * @route   POST /api/login
 * @desc    Authenticate user and return JWT
 * @access  Public
 */
router.post('/login', async (req, res) => {
  try {
    const { email, password } = req.body;

    // 1. Validate request body
    if (!email || !password) {
      return res.status(400).json({
        status: 'fail',
        message: 'Please provide email and password.',
      });
    }

    // 2. Find user by email, explicitly including the password field
    const user = await User.findOne({ email }).select('+password');

    // 3. Check if user exists and if the password is correct
    if (!user || !(await bcrypt.compare(password, user.password))) {
      // Use a generic message to prevent user enumeration attacks
      return res.status(401).json({
        status: 'fail',
        message: 'Invalid email or password.',
      });
    }

    // 4. If credentials are correct, generate and sign a JWT
    const payload = {
      id: user._id,
      role: user.role,
    };

    const secret = process.env.JWT_SECRET;
    const expiresIn = process.env.JWT_EXPIRES_IN || '1d';

    if (!secret) {
      console.error('JWT_SECRET is not defined in environment variables.');
      return res.status(500).json({
        status: 'error',
        message: 'Internal server configuration error.',
      });
    }

    const token = jwt.sign(payload, secret, { expiresIn });

    // 5. Send the token to the client
    res.status(200).json({
      status: 'success',
      token,
    });

  } catch (error) {
    console.error('Login endpoint error:', error);
    res.status(500).json({
      status: 'error',
      message: 'An internal server error occurred. Please try again later.',
    });
  }
});

module.exports = router;
