const winston = require('winston');

const logger = winston.createLogger({
  level: 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.json()
  ),
  transports: [
    new winston.transports.Console()
  ]
});

function requestLogger(req, res, next) {
  const start = Date.now();
  const timestamp = new Date().toISOString();
  const method = req.method;
  const url = req.originalUrl;
  const query = req.query;
  const headers = req.headers;

  res.on('finish', () => {
    const duration = Date.now() - start;
    const status = res.statusCode;

    logger.info({
      timestamp,
      method,
      url,
      query,
      headers,
      status,
      responseTime: `${duration}ms`
    });
  });

  next();
}

module.exports = requestLogger;
