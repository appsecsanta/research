const logger = console;

const errorHandler = (err, req, res, next) => {
  logger.error(err);

  const isDev = process.env.NODE_ENV === 'development';
  const statusCode = err.statusCode || 500;
  const message = isDev ? err.message : 'Internal Server Error';

  res.status(statusCode).json({
    message,
    ...(isDev && { stack: err.stack }),
  });
};

module.exports = errorHandler;
