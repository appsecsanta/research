/**
 * Express error handling middleware.
 *
 * This middleware should be placed at the end of the middleware stack.
 * It catches all errors, logs them, and sends an appropriate JSON response
 * based on the NODE_ENV environment variable.
 *
 * In 'development', it sends a detailed error message including the stack trace.
 * In 'production', it sends a generic, user-friendly error message to avoid
 * leaking sensitive information.
 *
 * @param {Error} err - The error object. Can have an optional `statusCode` property.
 * @param {import('express').Request} req - The Express request object.
 * @param {import('express').Response} res - The Express response object.
 * @param {import('express').NextFunction} next - The Express next middleware function.
 */
const errorHandler = (err, req, res, next) => {
  // In a real-world application, use a dedicated logger like Winston or Pino
  // instead of console.error.
  console.error(err);

  const statusCode = err.statusCode || 500;
  const isProduction = process.env.NODE_ENV === 'production';

  const responsePayload = {
    message: isProduction
      ? 'An unexpected error occurred on the server.'
      : err.message,
    // Only include the stack trace in non-production environments
    ...(isProduction ? null : { stack: err.stack }),
  };

  res.status(statusCode).json(responsePayload);
};

module.exports = errorHandler;
