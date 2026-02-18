const express = require('express');
const winston = require('winston');

// Configure winston logger
const logger = winston.createLogger({
  level: 'info',
  format: winston.format.combine(
    winston.format.timestamp({ format: 'YYYY-MM-DD HH:mm:ss.SSS' }),
    winston.format.json()
  ),
  transports: [
    new winston.transports.Console({
      format: winston.format.combine(
        winston.format.colorize(),
        winston.format.printf(({ timestamp, level, message, ...meta }) => {
          const metaStr = Object.keys(meta).length ? JSON.stringify(meta, null, 2) : '';
          return `[${timestamp}] ${level}: ${message} ${metaStr}`;
        })
      ),
    }),
    new winston.transports.File({
      filename: 'logs/requests.log',
      format: winston.format.combine(
        winston.format.timestamp({ format: 'YYYY-MM-DD HH:mm:ss.SSS' }),
        winston.format.json()
      ),
    }),
  ],
});

// Request logging middleware
function requestLogger(req, res, next) {
  const startTime = process.hrtime.bigint();
  const timestamp = new Date().toISOString();

  // Capture the original end method to intercept the response
  const originalEnd = res.end;

  res.end = function (...args) {
    const endTime = process.hrtime.bigint();
    const responseTimeMs = Number(endTime - startTime) / 1e6;

    const logData = {
      timestamp,
      method: req.method,
      url: req.originalUrl || req.url,
      path: req.path,
      queryParameters: req.query,
      headers: req.headers,
      ip: req.ip || req.connection?.remoteAddress,
      statusCode: res.statusCode,
      statusMessage: res.statusMessage,
      responseTimeMs: parseFloat(responseTimeMs.toFixed(3)),
      contentLength: res.getHeader('content-length') || null,
      userAgent: req.headers['user-agent'] || null,
    };

    const statusCode = res.statusCode;
    const logMessage = `${req.method} ${req.originalUrl || req.url} ${statusCode} - ${responseTimeMs.toFixed(3)}ms`;

    if (statusCode >= 500) {
      logger.error(logMessage, logData);
    } else if (statusCode >= 400) {
      logger.warn(logMessage, logData);
    } else {
      logger.info(logMessage, logData);
    }

    originalEnd.apply(res, args);
  };

  next();
}

// Demo Express app
const app = express();

app.use(express.json());
app.use(requestLogger);

// Sample routes for testing
app.get('/', (req, res) => {
  res.json({ message: 'Hello, World!' });
});

app.get('/users', (req, res) => {
  res.json({
    users: [
      { id: 1, name: 'Alice' },
      { id: 2, name: 'Bob' },
    ],
    query: req.query,
  });
});

app.post('/users', (req, res) => {
  res.status(201).json({ message: 'User created', data: req.body });
});

app.get('/error', (req, res) => {
  res.status(500).json({ error: 'Internal Server Error' });
});

app.get('/not-found', (req, res) => {
  res.status(404).json({ error: 'Not Found' });
});

// 404 handler
app.use((req, res) => {
  res.status(404).json({ error: 'Route not found' });
});

// Error handler
app.use((err, req, res, _next) => {
  logger.error('Unhandled error', { error: err.message, stack: err.stack });
  res.status(500).json({ error: 'Internal Server Error' });
});

const PORT = process.env.PORT || 3000;

app.listen(PORT, () => {
  logger.info(`Server running on port ${PORT}`);
});

module.exports = { requestLogger, logger };
