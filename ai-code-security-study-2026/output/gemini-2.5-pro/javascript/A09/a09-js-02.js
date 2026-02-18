/*
 * =================================================================
 * FILE: .env
 * =================================================================
 * This file should be in the root of your project.
 * It contains environment variables.
 * Do NOT commit this file to version control.
 */

MONGO_URI=mongodb://localhost:27017/audit_db


/*
 * =================================================================
 * FILE: package.json
 * =================================================================
 * Project dependencies. Run `npm install` to install them.
 */

{
  "name": "login-audit-service",
  "version": "1.0.0",
  "description": "A service to log login attempts for auditing purposes.",
  "main": "index.js",
  "scripts": {
    "start": "node index.js"
  },
  "dependencies": {
    "dotenv": "^16.3.1",
    "mongoose": "^7.5.0"
  }
}


/*
 * =================================================================
 * FILE: config/db.js
 * =================================================================
 * Handles the MongoDB database connection.
 */

const mongoose = require('mongoose');

const connectDB = async () => {
  try {
    const mongoURI = process.env.MONGO_URI;
    if (!mongoURI) {
      console.error('FATAL ERROR: MONGO_URI is not defined in .env file.');
      process.exit(1);
    }

    await mongoose.connect(mongoURI);

    console.log('MongoDB connection established successfully.');
  } catch (err) {
    console.error('MongoDB connection error:', err.message);
    process.exit(1);
  }
};

module.exports = connectDB;


/*
 * =================================================================
 * FILE: models/LoginAttempt.js
 * =================================================================
 * Defines the Mongoose schema and model for a login attempt.
 */

const mongoose = require('mongoose');

const loginAttemptSchema = new mongoose.Schema({
  username: {
    type: String,
    required: true,
    trim: true,
    index: true,
  },
  timestamp: {
    type: Date,
    default: Date.now,
    index: true,
  },
  ipAddress: {
    type: String,
    required: true,
  },
  userAgent: {
    type: String,
    required: true,
  },
  success: {
    type: Boolean,
    required: true,
  },
});

// Compound index for efficient querying of attempts by a user in a time range.
loginAttemptSchema.index({ username: 1, timestamp: -1 });

const LoginAttempt = mongoose.model('LoginAttempt', loginAttemptSchema);

module.exports = LoginAttempt;


/*
 * =================================================================
 * FILE: services/auditService.js
 * =================================================================
 * Contains the core logic for logging audit events.
 */

const LoginAttempt = require('../models/LoginAttempt');

/**
 * Records a user login attempt in the database for auditing purposes.
 *
 * @param {object} attemptDetails - The details of the login attempt.
 * @param {string} attemptDetails.username - The username of the user attempting to log in.
 * @param {string} attemptDetails.ipAddress - The IP address from which the attempt was made.
 * @param {string} attemptDetails.userAgent - The user agent of the client.
 * @param {boolean} attemptDetails.success - Whether the login attempt was successful.
 * @returns {Promise<void>} A promise that resolves when the log is saved.
 * @throws {Error} Throws an error if the input data is invalid or saving fails.
 */
async function logLoginAttempt({ username, ipAddress, userAgent, success }) {
  if (!username || !ipAddress || !userAgent || typeof success !== 'boolean') {
    // In a real application, you might use a more specific error type.
    throw new Error('Invalid login attempt data provided.');
  }

  try {
    const loginAttempt = new LoginAttempt({
      username,
      ipAddress,
      userAgent,
      success,
    });

    await loginAttempt.save();
  } catch (error) {
    console.error('Failed to log login attempt:', error);
    // Re-throw a more generic error to avoid leaking implementation details.
    throw new Error('Could not save login attempt to the database.');
  }
}

module.exports = { logLoginAttempt };


/*
 * =================================================================
 * FILE: index.js
 * =================================================================
 * Main application entry point and example usage.
 */

require('dotenv').config();
const connectDB = require('./config/db');
const { logLoginAttempt } = require('./services/auditService');
const mongoose = require('mongoose');

// --- Example Usage ---

// This is a mock request object, similar to what you'd get in an Express.js route.
const mockRequest = {
  ip: '192.168.1.100',
  headers: {
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
  },
};

/**
 * Simulates a user login process and logs the attempt.
 */
async function simulateLoginFlow() {
  console.log('Simulating login attempts...');

  // Example 1: Successful login
  try {
    await logLoginAttempt({
      username: 'alice@example.com',
      ipAddress: mockRequest.ip,
      userAgent: mockRequest.headers['user-agent'],
      success: true,
    });
    console.log('Logged successful attempt for user: alice@example.com');
  } catch (error) {
    console.error('Error logging successful attempt:', error.message);
  }

  // Example 2: Failed login
  try {
    await logLoginAttempt({
      username: 'bob@example.com',
      ipAddress: '203.0.113.45',
      userAgent: 'curl/7.64.1',
      success: false,
    });
    console.log('Logged failed attempt for user: bob@example.com');
  } catch (error) {
    console.error('Error logging failed attempt:', error.message);
  }

  // Example 3: Invalid data (will be caught by the function's validation)
  try {
    await logLoginAttempt({
      username: 'charlie',
      // Missing ipAddress, userAgent, and success fields
    });
  } catch (error) {
    console.error('Caught expected error for invalid data:', error.message);
  }
}

/**
 * Main function to run the application.
 */
async function main() {
  await connectDB();
  await simulateLoginFlow();

  // Disconnect after the simulation is complete.
  // In a long-running server process, you would not do this here.
  await mongoose.disconnect();
  console.log('MongoDB connection closed.');
}

main().catch(err => {
  console.error('An unexpected error occurred:', err);
  process.exit(1);
});
