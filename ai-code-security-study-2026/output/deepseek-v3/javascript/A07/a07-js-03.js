const express = require('express');
const cookieParser = require('cookie-parser');
const crypto = require('crypto');
const { User, RememberMeToken } = require('./models'); // Assuming you have User and RememberMeToken models

const app = express();
app.use(cookieParser());
app.use(express.json());

// Generate a random token
function generateToken() {
  return crypto.randomBytes(32).toString('hex');
}

// Middleware to check for remember me token
async function checkRememberMeToken(req, res, next) {
  if (!req.cookies.remember_me) return next();

  const token = req.cookies.remember_me;
  const rememberMeToken = await RememberMeToken.findOne({ where: { token } });

  if (rememberMeToken) {
    const user = await User.findByPk(rememberMeToken.userId);
    if (user) {
      req.user = user;
    }
  }

  next();
}

// Login route
app.post('/login', async (req, res) => {
  const { email, password, rememberMe } = req.body;
  const user = await User.findOne({ where: { email } });

  if (user && await user.validatePassword(password)) {
    req.session.userId = user.id;

    if (rememberMe) {
      const token = generateToken();
      const expiresAt = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000); // 30 days

      await RememberMeToken.create({
        token,
        userId: user.id,
        expiresAt
      });

      res.cookie('remember_me', token, { 
        httpOnly: true, 
        expires: expiresAt 
      });
    }

    res.json({ success: true });
  } else {
    res.status(401).json({ success: false, message: 'Invalid credentials' });
  }
});

// Logout route
app.post('/logout', async (req, res) => {
  if (req.cookies.remember_me) {
    const token = req.cookies.remember_me;
    await RememberMeToken.destroy({ where: { token } });
    res.clearCookie('remember_me');
  }

  req.session.destroy(() => {
    res.json({ success: true });
  });
});

// Protected route
app.get('/protected', checkRememberMeToken, (req, res) => {
  if (req.user) {
    res.json({ success: true, user: req.user });
  } else {
    res.status(401).json({ success: false, message: 'Unauthorized' });
  }
});

app.listen(3000, () => {
  console.log('Server running on port 3000');
});
