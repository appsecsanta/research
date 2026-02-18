const express = require('express');
const mongoose = require('mongoose');
const router = express.Router();

// User Schema
const userSchema = new mongoose.Schema({
  name: { type: String, required: true },
  email: { type: String, required: true, unique: true },
  role: {
    type: String,
    enum: ['user', 'moderator', 'admin'],
    default: 'user',
  },
  createdAt: { type: Date, default: Date.now },
  updatedAt: { type: Date, default: Date.now },
});

const User = mongoose.model('User', userSchema);

// Authentication middleware - verifies the user is logged in
const authenticate = async (req, res, next) => {
  try {
    const userId = req.headers['x-user-id'];

    if (!userId) {
      return res.status(401).json({ error: 'Authentication required' });
    }

    const user = await User.findById(userId);

    if (!user) {
      return res.status(401).json({ error: 'Invalid authentication credentials' });
    }

    req.user = user;
    next();
  } catch (error) {
    return res.status(401).json({ error: 'Authentication failed' });
  }
};

// Authorization middleware - verifies the user is an admin
const authorizeAdmin = (req, res, next) => {
  if (!req.user || req.user.role !== 'admin') {
    return res.status(403).json({ error: 'Forbidden: Admin access required' });
  }
  next();
};

// PUT /api/users/:id/role - Update a user's role (admin only)
router.put('/api/users/:id/role', authenticate, authorizeAdmin, async (req, res) => {
  try {
    const { id } = req.params;
    const { role } = req.body;

    // Validate role is provided
    if (!role) {
      return res.status(400).json({ error: 'Role is required in the request body' });
    }

    // Validate role value
    const validRoles = ['user', 'moderator', 'admin'];
    if (!validRoles.includes(role)) {
      return res.status(400).json({
        error: `Invalid role. Must be one of: ${validRoles.join(', ')}`,
      });
    }

    // Validate the target user ID
    if (!mongoose.Types.ObjectId.isValid(id)) {
      return res.status(400).json({ error: 'Invalid user ID format' });
    }

    // Prevent admin from changing their own role
    if (req.user._id.toString() === id) {
      return res.status(400).json({ error: 'Administrators cannot change their own role' });
    }

    // Find and update the user
    const updatedUser = await User.findByIdAndUpdate(
      id,
      {
        role,
        updatedAt: Date.now(),
      },
      {
        new: true,
        runValidators: true,
      }
    ).select('-__v');

    if (!updatedUser) {
      return res.status(404).json({ error: 'User not found' });
    }

    return res.status(200).json({
      message: `User role updated successfully to '${role}'`,
      user: updatedUser,
    });
  } catch (error) {
    console.error('Error updating user role:', error);
    return res.status(500).json({ error: 'Internal server error' });
  }
});

// Express app setup
const app = express();
app.use(express.json());
app.use(router);

// Database connection and server start
const PORT = process.env.PORT || 3000;
const MONGO_URI = process.env.MONGO_URI || 'mongodb://localhost:27017/myapp';

mongoose
  .connect(MONGO_URI)
  .then(() => {
    console.log('Connected to MongoDB');
    app.listen(PORT, () => {
      console.log(`Server running on port ${PORT}`);
    });
  })
  .catch((error) => {
    console.error('MongoDB connection error:', error);
    process.exit(1);
  });

module.exports = { app, router, User };
