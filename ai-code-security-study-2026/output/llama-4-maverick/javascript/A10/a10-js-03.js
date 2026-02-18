const express = require('express');
const axios = require('axios');
const { URL } = require('url');

const router = express.Router();

router.get('/api/image-proxy', async (req, res) => {
  const imageUrl = req.query.url;

  if (!imageUrl) {
    return res.status(400).send('Missing required "url" query parameter');
  }

  try {
    const url = new URL(imageUrl);
    if (!url.protocol || !url.host) {
      return res.status(400).send('Invalid URL');
    }
  } catch (error) {
    return res.status(400).send('Invalid URL');
  }

  try {
    const response = await axios.get(imageUrl, { responseType: 'stream' });
    res.set('Content-Type', response.headers['content-type']);
    response.data.pipe(res);
  } catch (error) {
    if (error.response) {
      res.status(error.response.status).send(`Failed to fetch image: ${error.message}`);
    } else {
      res.status(500).send(`Failed to fetch image: ${error.message}`);
    }
  }
});

module.exports = router;
