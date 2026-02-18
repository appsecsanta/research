const winston = require('winston');

/**
 * Creates a Winston logger instance.
 * In a real application, this would likely be in its own module.
 */
const logger = winston.createLogger({
  level: 'info',
  format: winston.format.combine(
    winston.format.timestamp({
      format: 'YYYY-MM-DD HH:mm:ss'
    }),
    winston.format.errors({ stack: true }),
    winston.format.splat(),
    winston.format.json()
  ),
  defaultMeta: { service: 'user-service' },
  transports: [
    // - Write all logs with importance level of `error` or less to `error.log`
    // - Write all logs with importance level of `info` or less to `combined.log`
    // new winston.transports.File({ filename: 'error.log', level: 'error' }),
    // new winston.transports.File({ filename: 'combined.log' }),
  ],
});

//
// If we're not in production then log to the `console` with the format:
// `${info.level}: ${info.message} JSON.stringify({ ...rest }) `
//
if (process.env.NODE_ENV !== 'production') {
  logger.add(new winston.transports.Console({
    format: winston.format.combine(
      winston.format.colorize(),
      wston.format.simple()
    ),
  }));
}


/**
 * Express middleware to log incoming HTTP requests.
 *
 * This middleware captures detailed information about each request and its corresponding response,
 * including timing, status, and headers. It uses the 'finish' event on the response object
 * to ensure that response details like status code and timing are accurate.
 *
 * @param {import('express').Request} req - The Express request object.
 * @param {import('express').Response} res - The Express response object.
 * @param {import('express').NextFunction} next - The next middleware function.
 */
const requestLogger = (req, res, next) => {
  const start = process.hrtime();
  const requestTimestamp = new Date();

  const { method, originalUrl, query, headers, body } = req;

  // The 'finish' event is emitted when the response has been sent.
  res.on('finish', () => {
    const diff = process.hrtime(start);
    const responseTimeInMs = (diff[0] * 1e3 + diff[1] * 1e-6).toFixed(3);
    const { statusCode } = res;

    const logDetails = {
      timestamp: requestTimestamp.toISOString(),
      method,
      url: originalUrl,
      query,
      // WARNING: Logging headers and body in production can expose sensitive data.
      // Redact or omit sensitive fields like 'Authorization', passwords, etc.
      headers,
      // body, // Uncomment to log request body, but be cautious with large or sensitive payloads.
      statusCode,
      responseTime: `${responseTimeInMs}ms`,
    };

    if (statusCode >= 400) {
      logger.error('HTTP Request Error', logDetails);
    } else {
      logger.info('HTTP Request', logDetails);
    }
  });

  next();
};

module.exports = requestLogger;

/*
// --- Example Usage in an Express App ---

const express = require('express');
const requestLogger = require('./requestLogger'); // Assuming the middleware is in this file

const app = express();
const PORT = 3000;

// Place the logger middleware before all your routes.
app.use(requestLogger);

// Example routes
app.get('/', (req, res) => {
  res.status(200).send('Hello World!');
});

app.get('/data', (req, res) => {
  setTimeout(() => {
    res.status(200).json({ message: 'This is some data.' });
  }, 500); // Simulate a delay
});

app.get('/error', (req, res) => {
  res.status(500).send('This is a simulated error.');
});

app.listen(PORT, () => {
  console.log(`Server is running on http://localhost:${PORT}`);
});

*/
