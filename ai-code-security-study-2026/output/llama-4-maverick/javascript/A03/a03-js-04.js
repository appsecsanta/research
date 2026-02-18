// controllers/userController.js
const express = require('express');
const router = express.Router();
const User = require('../models/User');

router.post('/profile', async (req, res) => {
  try {
    const { displayName, bio } = req.body;
    const user = await User.create({ displayName, bio });
    res.redirect(`/profile/${user.id}`);
  } catch (error) {
    console.error(error);
    res.status(500).send('Error creating user profile');
  }
});

router.get('/profile/:id', async (req, res) => {
  try {
    const user = await User.findByPk(req.params.id);
    if (!user) {
      return res.status(404).send('User not found');
    }
    res.render('profile', { user });
  } catch (error) {
    console.error(error);
    res.status(500).send('Error fetching user profile');
  }
});

module.exports = router;
