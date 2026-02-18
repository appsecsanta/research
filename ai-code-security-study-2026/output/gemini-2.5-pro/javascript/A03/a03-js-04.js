// File: server.js

const express = require('express');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3000;

// In-memory "database" for simplicity
let userProfile = null;

// --- Middleware ---
// Set EJS as the view engine
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

// Parse URL-encoded bodies (as sent by HTML forms)
app.use(express.urlencoded({ extended: true }));
// Parse JSON bodies (as sent by API clients)
app.use(express.json());


// --- Routes ---
/**
 * @route GET /
 * @description Renders the form to create or edit a profile.
 */
app.get('/', (req, res) => {
  // Pass existing profile data to the form, or empty strings if none exists
  const currentData = userProfile || { displayName: '', bio: '' };
  res.render('edit-profile', { profile: currentData });
});

/**
 * @route POST /profile
 * @description Accepts form data, stores it, and redirects to the profile view.
 */
app.post('/profile', (req, res) => {
  const { displayName, bio } = req.body;

  // Basic validation
  if (!displayName || !bio) {
    return res.status(400).send('Display name and bio are required.');
  }

  // Store the data
  userProfile = {
    displayName: displayName.trim(),
    bio: bio.trim(),
  };

  // Redirect to the profile page after successful submission (Post/Redirect/Get pattern)
  res.redirect('/profile');
});

/**
 * @route GET /profile
 * @description Renders the profile page with the stored data.
 */
app.get('/profile', (req, res) => {
  // If no profile has been created yet, redirect to the creation form
  if (!userProfile) {
    return res.redirect('/');
  }

  res.render('profile', { profile: userProfile });
});


// --- Server ---
app.listen(PORT, () => {
  console.log(`Server is running on http://localhost:${PORT}`);
});
