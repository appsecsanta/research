const express = require('express');

const errorHandler = (err, req, res, next) => {
    const isProduction = process.env.NODE_ENV === 'production';

    // Log the error for debugging
    console.error(err);

    // Determine the response based on the environment
    const response = isProduction
        ? { message: 'Something went wrong!' }
        : { message: err.message, stack: err.stack };

    // Send the response with appropriate status code
    res.status(err.status || 500).json(response);
};

module.exports = errorHandler;
