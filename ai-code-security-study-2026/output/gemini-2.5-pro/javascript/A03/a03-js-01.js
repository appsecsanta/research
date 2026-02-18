const express = require('express');
const { MongoClient, ServerApiVersion } = require('mongodb');

// --- Configuration ---
const PORT = process.env.PORT || 3000;
// It's highly recommended to use environment variables for sensitive data
const MONGO_URI = process.env.MONGO_URI || 'mongodb://localhost:27017';
const DB_NAME = 'yourAppDb';
const COLLECTION_NAME = 'users';

// --- Express App Initialization ---
const app = express();
app.use(express.json());

// --- MongoDB Client Initialization ---
const client = new MongoClient(MONGO_URI, {
  serverApi: {
    version: ServerApiVersion.v1,
    strict: true,
    deprecationErrors: true,
  }
});

let db;

/**
 * Connects to MongoDB and starts the Express server.
 */
async function startServer() {
  try {
    // Connect the client to the server
    await client.connect();
    db = client.db(DB_NAME);
    console.log("Successfully connected to MongoDB.");

    // Optional: Create a unique index on username to prevent duplicates
    await db.collection(COLLECTION_NAME).createIndex({ username: 1 }, { unique: true });

    app.listen(PORT, () => {
      console.log(`Server is running on http://localhost:${PORT}`);
    });
  } catch (err) {
    console.error("Failed to connect to MongoDB or start server", err);
    process.exit(1);
  }
}

// --- API Endpoints ---

/**
 * POST /api/login
 * Authenticates a user based on username and password.
 * @param {string} req.body.username - The user's username.
 * @param {string} req.body.password - The user's password.
 */
app.post('/api/login', async (req, res) => {
  try {
    const { username, password } = req.body;

    if (!username || !password) {
      return res.status(400).json({ message: 'Username and password are required.' });
    }

    const usersCollection = db.collection(COLLECTION_NAME);

    // SECURITY WARNING: In a production environment, NEVER store passwords in plaintext.
    // Always hash passwords using a strong, salted hashing algorithm like bcrypt.
    // The query would then be:
    // 1. Find user by username: `const user = await usersCollection.findOne({ username });`
    // 2. Compare hashed password: `if (user && await bcrypt.compare(password, user.passwordHash)) { ... }`
    const user = await usersCollection.findOne({ username, password });

    if (user) {
      // Successful login
      // Avoid sending sensitive information like the password back to the client
      const { password, ...userToSend } = user;
      res.status(200).json({
        message: 'Login successful',
        user: userToSend
      });
    } else {
      // Failed login
      res.status(401).json({ message: 'Invalid username or password' });
    }
  } catch (error) {
    console.error('Login error:', error);
    res.status(500).json({ message: 'An internal server error occurred' });
  }
});


// --- Start the application ---
startServer();
