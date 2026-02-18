const express = require('express');
const winston = require('winston');

const logger = winston.createLogger({
  level: 'info',
  format: winston.format.json(),
  transports: [
    new winston.transports.Console()
  ]
});

const logMiddleware = (req, res, next) => {
  const startTime = Date.now();

  res.on('finish', () => {
    const responseTime = Date.now() - startTime;

    logger.info({
      timestamp: new Date().toISOString(),
      method: req.method,
      url: req.originalUrl,
      query: req.query,
      headers: req.headers,
      statusCode: res.statusCode,
      responseTime: `${responseTime}ms`
    });
  });

  next();
};

module.exports = logMiddleware;
