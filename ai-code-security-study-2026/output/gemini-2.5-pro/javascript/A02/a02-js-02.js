import { randomBytes, createHash } from 'crypto';
import express from 'express';

// --- Token Generation ---

/**
 * Generates a cryptographically secure, URL-safe token and its hash.
 * The raw token is for the user (sent in the email link).
 * The hash is for you (stored in the database).
 *
 * @returns {{token: string, hashedToken: string}} An object containing the raw token and its SHA-256 hash.
 */
export const generateVerificationToken = () => {
  // Generate a 32-byte random token
  const token = randomBytes(32).toString('hex');

  // Hash the token to store in the database
  const hashedToken = createHash('sha256').update(token).digest('hex');

  // In your user registration logic, you would:
  // 1. Save `hashedToken` and an expiry date to the user's record in the database.
  // 2. Send the raw `token` to the user's email.

  return { token, hashedToken };
};


// --- Express Verification Endpoint ---

// This is a mock database layer. In a real application, these functions
// would execute queries against your database (e.g., PostgreSQL, MongoDB).
const db = {
  /**
   * Finds a user by their verification token hash.
   * The query should also check that the token has not expired.
   */
  async findUserByTokenHash(hashedToken) {
    // PSEUDOCODE:
    // const user = await UserModel.findOne({
    //   'emailVerification.tokenHash': hashedToken,
    //   'emailVerification.expiresAt': { $gt: new Date() }
    // });
    // return user;
    console.log(`DATABASE: Searching for user with token hash: ${hashedToken.substring(0, 10)}...`);
    // Mock response: returning a user if the token is "valid" for demonstration.
    if (hashedToken) {
      return { id: 'user_abc_123', isVerified: false };
    }
    return null;
  },

  /**
   * Marks a user's email as verified.
   */
  async verifyUser(userId) {
    // PSEUDOCODE:
    // await UserModel.updateOne(
    //   { _id: userId },
    //   { isVerified: true, $unset: { emailVerification: "" } }
    // );
    console.log(`DATABASE: Marking user ${userId} as verified.`);
  },
};


/**
 * Express middleware to handle email verification.
 * It expects the verification token in the query string: `/verify?token=...`
 *
 * @param {express.Request} req - The Express request object.
 * @param {express.Response} res - The Express response object.
 */
export const verifyEmailEndpoint = async (req, res) => {
  const { token } = req.query;

  if (!token || typeof token !== 'string') {
    return res.status(400).json({
      error: 'Bad Request',
      message: 'Verification token is missing or invalid.',
    });
  }

  try {
    const hashedToken = createHash('sha256').update(token).digest('hex');

    // 1. Find a user with a matching, unexpired token.
    const user = await db.findUserByTokenHash(hashedToken);

    if (!user) {
      return res.status(400).json({
        error: 'Invalid Token',
        message: 'Verification link is invalid or has expired. Please request a new one.',
      });
    }

    if (user.isVerified) {
      return res.status(400).json({
        error: 'Already Verified',
        message: 'This email address has already been verified.',
      });
    }

    // 2. Mark the user as verified and remove the token information.
    await db.verifyUser(user.id);

    // 3. Respond with success. In a real web application, you would
    // likely redirect the user to a "verification successful" page.
    // e.g., res.redirect('/verification-success');
    return res.status(200).json({ message: 'Email verified successfully.' });

  } catch (error) {
    console.error('Email verification failed:', error);
    return res.status(500).json({
      error: 'Internal Server Error',
      message: 'An unexpected error occurred during verification.',
    });
  }
};
