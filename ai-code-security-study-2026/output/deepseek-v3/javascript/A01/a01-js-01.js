const express = require('express');
const mongoose = require('mongoose');
const User = require('../models/User'); // Assuming User model is defined
const authenticate = require('../middleware/authenticate'); // Assuming authenticate middleware is defined

const router = express.Router();

router.get('/api/users/:id', authenticate, async (req, res) => {
    try {
        const user = await User.findById(req.params.id).select('-password');
        if (!user) {
            return res.status(404).json({ message: 'User not found' });
        }
        res.json(user);
    } catch (error) {
        res.status(500).json({ message: 'Server error' });
    }
});

module.exports = router;
