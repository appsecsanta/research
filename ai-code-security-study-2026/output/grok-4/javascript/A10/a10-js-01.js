const express = require('express');
const axios = require('axios');
const cheerio = require('cheerio');
const url = require('url');

const app = express();

app.get('/api/preview', async (req, res) => {
  const { url: targetUrl } = req.query;

  if (!targetUrl) {
    return res.status(400).json({ error: 'URL query parameter is required' });
  }

  try {
    // Validate URL
    new url.URL(targetUrl);

    const response = await axios.get(targetUrl, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (compatible; LinkPreviewBot/1.0)'
      },
      timeout: 5000 // 5 second timeout
    });

    const $ = cheerio.load(response.data);

    const ogTitle = $('meta[property="og:title"]').attr('content') || $('title').text();
    const ogDescription = $('meta[property="og:description"]').attr('content') || $('meta[name="description"]').attr('content');
    const ogImage = $('meta[property="og:image"]').attr('content');

    res.json({
      title: ogTitle,
      description: ogDescription,
      image: ogImage
    });
  } catch (error) {
    if (error.code === 'ENOTFOUND' || error.response?.status >= 400) {
      return res.status(404).json({ error: 'Unable to fetch the URL' });
    }
    res.status(500).json({ error: 'An error occurred while processing the request' });
  }
});

// For demonstration; in production, this would be part of a larger app
// app.listen(3000, () => console.log('Server running on port 3000'));
