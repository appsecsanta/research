const express = require('express');
const axios = require('axios');
const cheerio = require('cheerio');

const app = express();
const PORT = process.env.PORT || 3000;

// In-memory cache with TTL
const cache = new Map();
const CACHE_TTL = 60 * 60 * 1000; // 1 hour

function getCached(url) {
  const entry = cache.get(url);
  if (entry && Date.now() - entry.timestamp < CACHE_TTL) {
    return entry.data;
  }
  cache.delete(url);
  return null;
}

function setCache(url, data) {
  cache.set(url, { data, timestamp: Date.now() });
}

function isValidUrl(string) {
  try {
    const url = new URL(string);
    return url.protocol === 'http:' || url.protocol === 'https:';
  } catch {
    return false;
  }
}

function extractOpenGraphTags(html, url) {
  const $ = cheerio.load(html);

  const getMetaContent = (property) => {
    return (
      $(`meta[property="${property}"]`).attr('content') ||
      $(`meta[name="${property}"]`).attr('content') ||
      null
    );
  };

  const ogTitle =
    getMetaContent('og:title') ||
    $('title').text().trim() ||
    null;

  const ogDescription =
    getMetaContent('og:description') ||
    getMetaContent('description') ||
    null;

  const ogImage = getMetaContent('og:image') || null;

  const ogUrl = getMetaContent('og:url') || url;
  const ogSiteName = getMetaContent('og:site_name') || null;
  const ogType = getMetaContent('og:type') || null;

  // Twitter card fallbacks
  const twitterTitle = getMetaContent('twitter:title') || null;
  const twitterDescription = getMetaContent('twitter:description') || null;
  const twitterImage =
    getMetaContent('twitter:image') ||
    getMetaContent('twitter:image:src') ||
    null;

  // Resolve relative image URLs
  let image = ogImage || twitterImage;
  if (image && !image.startsWith('http')) {
    try {
      image = new URL(image, url).href;
    } catch {
      // leave as-is if URL resolution fails
    }
  }

  return {
    title: ogTitle || twitterTitle || null,
    description: ogDescription || twitterDescription || null,
    image,
    url: ogUrl,
    siteName: ogSiteName,
    type: ogType,
  };
}

app.get('/api/preview', async (req, res) => {
  const { url } = req.query;

  if (!url) {
    return res.status(400).json({
      error: 'Missing required query parameter: url',
    });
  }

  if (!isValidUrl(url)) {
    return res.status(400).json({
      error: 'Invalid URL. Must be a valid HTTP or HTTPS URL.',
    });
  }

  // Check cache
  const cached = getCached(url);
  if (cached) {
    return res.json({ success: true, data: cached, cached: true });
  }

  try {
    const response = await axios.get(url, {
      timeout: 10000,
      maxRedirects: 5,
      headers: {
        'User-Agent':
          'Mozilla/5.0 (compatible; LinkPreviewBot/1.0; +https://example.com/bot)',
        Accept: 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
      },
      // Only accept text/html responses
      validateStatus: (status) => status >= 200 && status < 300,
      maxContentLength: 5 * 1024 * 1024, // 5MB limit
      responseType: 'text',
    });

    const contentType = response.headers['content-type'] || '';
    if (!contentType.includes('text/html') && !contentType.includes('application/xhtml+xml')) {
      return res.status(422).json({
        error: 'URL does not point to an HTML page.',
      });
    }

    const data = extractOpenGraphTags(response.data, url);

    setCache(url, data);

    return res.json({ success: true, data, cached: false });
  } catch (error) {
    if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      return res.status(504).json({
        error: 'Request to the provided URL timed out.',
      });
    }

    if (error.response) {
      return res.status(502).json({
        error: `Failed to fetch URL. Remote server responded with status ${error.response.status}.`,
      });
    }

    if (error.code === 'ENOTFOUND' || error.code === 'ECONNREFUSED') {
      return res.status(502).json({
        error: 'Could not connect to the provided URL.',
      });
    }

    console.error('Preview fetch error:', error.message);
    return res.status(500).json({
      error: 'An unexpected error occurred while fetching the link preview.',
    });
  }
});

app.listen(PORT, () => {
  console.log(`Link preview server running on port ${PORT}`);
});

module.exports = app;
