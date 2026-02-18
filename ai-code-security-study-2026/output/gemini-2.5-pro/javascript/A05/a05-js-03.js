/**
 * File: app.js
 * Description: Example Express application setup.
 *
 * To run:
 * 1. npm init -y
 * 2. npm install express
 * 3. Create the directory structure:
 *    - app.js
 *    - middleware/errorHandler.js
 *    - utils/appError.js
 * 4. node app.js
 * 5. For production mode: NODE_ENV=production node app.js
 */
const express = require('express');
const AppError = require('./utils/appError');
const globalErrorHandler = require('./middleware/errorHandler');

const app = express();

app.use(express.json());

// --- ROUTES ---
app.get('/success', (req, res) => {
  res.status(200).json({
    status: 'success',
    message: 'This is a success route.',
  });
});

// Example of a handled, operational error
app.get('/fail', (req, res, next) => {
  // Pass the error to the next middleware in the stack (our error handler)
  next(new AppError('The resource you requested was not found.', 404));
});

// Example of an unhandled, programming error (crash)
app.get('/crash', (req, res, next) => {
  // This will throw an unhandled error that our middleware will catch
  const x = {};
  console.log(x.y.z); // TypeError: Cannot read properties of undefined
});

// Catch all unhandled routes and forward to error handler
app.all('*', (req, res, next) => {
  next(new AppError(`Can't find ${req.originalUrl} on this server!`, 404));
});

// --- GLOBAL ERROR HANDLING MIDDLEWARE ---
// This must be the last app.use() call.
// Express knows it's an error handler because it has 4 arguments.
app.use(globalErrorHandler);

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`App running on port ${PORT}...`);
  console.log(`Current environment: ${process.env.NODE_ENV || 'development'}`);
});
