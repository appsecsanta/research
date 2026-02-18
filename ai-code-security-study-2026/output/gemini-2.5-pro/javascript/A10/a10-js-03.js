const express = require('express');
const axios = require('axios');
const { URL } = require('url');

const app = express();
const PORT = process.env.PORT || 3000;

/**
 * GET /api/image-proxy
 * Proxies an image from a remote URL to avoid mixed content issues.
 * Query parameters:
 *   - url: The full URL of the image to proxy.
 */
app.get('/api/image-proxy', async (req, res) => {
  const { url } = req.query;

  // 1. Validate the URL parameter
  if (!url || typeof url !== 'string') {
    return res.status(400).json({
      error: 'URL query parameter is required and must be a string.'
    });
  }

  let imageUrl;
  try {
    imageUrl = new URL(url);
  } catch (error) {
    return res.status(400).json({
      error: 'Invalid URL format.'
    });
  }

  if (imageUrl.protocol !== 'http:' && imageUrl.protocol !== 'https:') {
    return res.status(400).json({
      error: 'URL must use http or https protocol.'
    });
  }

  try {
    // 2. Fetch the image from the remote server as a stream
    const imageResponse = await axios({
      method: 'get',
      url: imageUrl.href,
      responseType: 'stream',
      timeout: 10000, // 10-second timeout
      // Set a user-agent to mimic a browser and avoid being blocked
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'
      }
    });

    // 3. Validate the content type of the response
    const contentType = imageResponse.headers['content-type'];
    if (!contentType || !contentType.startsWith('image/')) {
      return res.status(400).json({
        error: 'The requested URL did not return an image.'
      });
    }

    // 4. Set response headers
    // Pass through the original content type
    res.setHeader('Content-Type', contentType);

    // Pass through content length if available
    if (imageResponse.headers['content-length']) {
      res.setHeader('Content-Length', imageResponse.headers['content-length']);
    }

    // Set caching headers to allow client and CDN caching
    res.setHeader('Cache-Control', 'public, max-age=86400'); // Cache for 1 day
    res.setHeader('X-Content-Type-Options', 'nosniff');

    // 5. Pipe the image stream directly to the client's response
    imageResponse.data.pipe(res);

    // Handle potential errors during the stream
    imageResponse.data.on('error', (streamError) => {
      console.error('Stream error while proxying image:', streamError);
      if (!res.headersSent) {
        res.status(500).json({
          error: 'Error streaming the image.'
        });
      } else {
        // If headers are already sent, we can only end the connection
        res.end();
      }
    });

  } catch (error) {
    // 6. Handle errors from the axios request
    if (axios.isAxiosError(error)) {
      console.error(`Axios error fetching image from ${url}:`, error.message);
      if (error.response) {
        // The remote server responded with an error status code
        const {
          status,
          statusText
        } = error.response;
        return res.status(status).json({
          error: `Remote server responded with ${status} ${statusText}`
        });
      } else if (error.request) {
        // The request was made but no response was received (e.g., timeout, network error)
        return res.status(502).json({
          error: 'Bad Gateway: No response from remote server.'
        });
      }
    }
    // Handle other unexpected errors
    console.error(`Unexpected error fetching image from ${url}:`, error);
    return res.status(500).json({
      error: 'An unexpected internal server error occurred.'
    });
  }
});

// Basic 404 handler for unhandled routes
app.use((req, res) => {
  res.status(404).json({
    error: 'Not Found'
  });
});

// Global error handler
app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(500).json({
    error: 'An internal server error occurred.'
  });
});

app.listen(PORT, () => {
  console.log(`Image proxy server running on http://localhost:${PORT}`);
  console.log(`Example usage: http://localhost:${PORT}/api/image-proxy?url=https://via.placeholder.com/150`);
});
