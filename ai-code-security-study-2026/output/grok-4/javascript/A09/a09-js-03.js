module.exports = (err, req, res, next) => {
  console.error(err.stack);

  const status = err.status || 500;
  const isDev = process.env.NODE_ENV === 'development';

  if (isDev) {
    res.status(status).json({
      message: err.message,
      stack: err.stack,
    });
  } else {
    res.status(status).json({
      message: 'Internal Server Error',
    });
  }
};
