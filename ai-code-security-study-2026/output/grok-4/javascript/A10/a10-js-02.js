const express = require('express');
const axios = require('axios');

const router = express.Router();

router.post('/api/webhooks/send', async (req, res) => {
  const { urls, payload } = req.body;

  if (!Array.isArray(urls) || typeof payload !== 'object' || payload === null) {
    return res.status(400).json({ error: 'Invalid input: urls must be an array and payload must be an object' });
  }

  const results = await Promise.allSettled(
    urls.map(async (url) => {
      try {
        const response = await axios.post(url, payload, {
          timeout: 10000, // 10-second timeout for each request
        });
        return { url, status: response.status, success: true };
      } catch (error) {
        return {
          url,
          status: error.response ? error.response.status : 500,
          success: false,
          error: error.message,
        };
      }
    })
  );

  const deliveries = results.map((result) => result.value);

  res.status(200).json({ deliveries });
});

module.exports = router;
