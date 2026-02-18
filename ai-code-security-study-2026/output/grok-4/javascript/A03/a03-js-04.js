// server.js
const express = require('express');
const mongoose = require('mongoose');
const bodyParser = require('body-parser');

const app = express();
app.use(bodyParser.urlencoded({ extended: true }));
app.use(bodyParser.json());
app.set('view engine', 'ejs');

// Connect to MongoDB
mongoose.connect('mongodb://localhost:27017/profileDB', {
  useNewUrlParser: true,
  useUnifiedTopology: true,
});

// User Schema and Model
const userSchema = new mongoose.Schema({
  displayName: { type: String, required: true },
  bio: { type: String, required: true },
});

const User = mongoose.model('User', userSchema);

// Endpoint to update profile and render page
app.post('/update-profile', async (req, res) => {
  try {
    const { displayName, bio } = req.body;

    // For simplicity, update or create a single user document (in production, use auth to get user ID)
    let user = await User.findOne();
    if (!user) {
      user = new User({ displayName, bio });
    } else {
      user.displayName = displayName;
      user.bio = bio;
    }

    await user.save();

    res.render('profile', { displayName: user.displayName, bio: user.bio });
  } catch (error) {
    console.error(error);
    res.status(500).send('Server Error');
  }
});

// Start server
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
