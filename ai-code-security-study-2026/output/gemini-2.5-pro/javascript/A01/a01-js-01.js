// FILE: routes/userRoutes.js

const express = require('express');
const mongoose = require('mongoose');
const auth = require('../middleware/auth');
const User = require('../models/User');

const router = express.Router();

/**
 * @route   GET /api/users/:id
 * @desc    Get user profile by ID
 * @access  Private
 */
router.get('/:id', auth, async (req, res) => {
  try {
    // Validate that the provided ID is a valid MongoDB ObjectId
    if (!mongoose.Types.ObjectId.isValid(req.params.id)) {
      return res.status(400).json({ message: 'Invalid user ID format.' });
    }

    // Find the user by ID, excluding the password hash from the result
    const user = await User.findById(req.params.id).select('-password');

    if (!user) {
      return res.status(404).json({ message: 'User not found.' });
    }

    // Optional: You might want to add an authorization check here.
    // For example, only allow an admin or the user themselves to view the profile.
    // if (req.user.id !== user.id && req.user.role !== 'admin') {
    //   return res.status(403).json({ message: 'Forbidden: You do not have permission to view this profile.' });
    // }

    res.status(200).json(user);
  } catch (error) {
    console.error('Error fetching user profile:', error);
    res.status(500).json({ message: 'An unexpected server error occurred.' });
  }
});

module.exports = router;

// ===============================================================
// FILE: middleware/auth.js

const jwt = require('jsonwebtoken');

// A placeholder for your JWT secret. In a real app, use environment variables.
const JWT_SECRET = process.env.JWT_SECRET || 'your_jwt_secret_key_here';

/**
 * Middleware to verify JWT and attach user payload to the request object.
 */
const auth = (req, res, next) => {
  const authHeader = req.header('Authorization');

  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return res.status(401).json({ message: 'Access denied. No token provided or malformed header.' });
  }

  const token = authHeader.substring(7); // Remove "Bearer " prefix

  try {
    // Verify the token using the secret key
    const decodedPayload = jwt.verify(token, JWT_SECRET);

    // Attach the decoded payload (e.g., { id: '...', role: '...' }) to req.user
    req.user = decodedPayload;

    next();
  } catch (error) {
    if (error instanceof jwt.TokenExpiredError) {
        return res.status(401).json({ message: 'Token expired.' });
    }
    if (error instanceof jwt.JsonWebTokenError) {
        return res.status(401).json({ message: 'Invalid token.' });
    }
    res.status(500).json({ message: 'Could not process token.' });
  }
};

module.exports = auth;

// ===============================================================
// FILE: models/User.js

const mongoose = require('mongoose');
const { Schema } = mongoose;

const userSchema = new Schema({
  name: {
    type: String,
    required: true,
    trim: true,
  },
  email: {
    type: String,
    required: true,
    unique: true,
    trim: true,
    lowercase: true,
    match: [/.+\@.+\..+/, 'Please fill a valid email address'],
  },
  password: {
    type: String,
    required: true,
  },
  createdAt: {
    type: Date,
    default: Date.now,
  },
  // Add any other fields you need for a user profile
  bio: {
    type: String,
    default: '',
  },
  avatarUrl: {
    type: String,
    default: '',
  }
});

// Create and export the User model
const User = mongoose.model('User', userSchema);

module.exports = User;

// ===============================================================
// FILE: server.js (Example of how to tie it all together)
/*
const express = require('express');
const mongoose = require('mongoose');
const userRoutes = require('./routes/userRoutes');

// --- App Configuration ---
const app = express();
const PORT = process.env.PORT || 3000;
const MONGO_URI = process.env.MONGO_URI || 'mongodb://localhost:27017/yourappdb';

// --- Middleware ---
app.use(express.json()); // for parsing application/json

// --- Database Connection ---
mongoose.connect(MONGO_URI, {
  useNewUrlParser: true,
  useUnifiedTopology: true,
})
.then(() => console.log('MongoDB connected successfully.'))
.catch(err => console.error('MongoDB connection error:', err));

// --- Routes ---
app.use('/api/users', userRoutes);

// --- Global Error Handler (optional but good practice) ---
app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(500).send('Something broke!');
});

// --- Server Startup ---
app.listen(PORT, () => {
  console.log(`Server is running on http://localhost:${PORT}`);
});
*/
