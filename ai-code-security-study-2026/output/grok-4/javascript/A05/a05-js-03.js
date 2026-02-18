module.exports = (err, req, res, next) => {
  // Log the error for debugging
  console.error(err.stack);

  // Determine status code and message
  const status = err.status || 500;
  const message = err.message || 'Internal Server Error';

  // Send JSON response
  res.status(status).json({ error: message });
};
