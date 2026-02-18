// server.js
const express = require('express');
const bodyParser = require('body-parser');
const mongoose = require('mongoose');

const app = express();
app.use(bodyParser.urlencoded({ extended: true }));
app.set('view engine', 'ejs');

mongoose.connect('mongodb://localhost:27017/userDB', { useNewUrlParser: true, useUnifiedTopology: true });

const userSchema = new mongoose.Schema({
  displayName: String,
  bio: String
});

const User = mongoose.model('User', userSchema);

app.get('/', (req, res) => {
  res.render('profile', { displayName: '', bio: '' });
});

app.post('/profile', (req, res) => {
  const newUser = new User({
    displayName: req.body.displayName,
    bio: req.body.bio
  });

  newUser.save((err) => {
    if (err) {
      console.log(err);
    } else {
      res.render('profile', { displayName: req.body.displayName, bio: req.body.bio });
    }
  });
});

app.listen(3000, () => {
  console.log('Server started on port 3000');
});
