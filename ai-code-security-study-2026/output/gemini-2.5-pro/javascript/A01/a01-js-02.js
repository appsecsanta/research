const express = require('express');
const fs = require('fs');
const path = require('path');
const mime = require('mime-types');

const app = express();
const PORT = process.env.PORT || 3000;

// Use path.resolve for a consistent, absolute path.
const UPLOADS_DIR = path.resolve(__dirname, 'uploads');

// Ensure the uploads directory exists.
// In a real application, this might be handled by a deployment script.
if (!fs.existsSync(UPLOADS_DIR)) {
  fs.mkdirSync(UPLOADS_DIR, { recursive: true });
}

app.get('/files', (req, res) => {
  const { filename } = req.query;

  if (!filename || typeof filename !== 'string') {
    return res.status(400).send('Bad Request: A "filename" query parameter is required.');
  }

  // Security: Use path.basename to prevent directory traversal attacks.
  // This extracts the last part of the path, ignoring any directory manipulators like '..'.
  const safeFilename = path.basename(filename);
  const filePath = path.join(UPLOADS_DIR, safeFilename);

  // Security: A redundant check to ensure the resolved path is still within the intended directory.
  if (!filePath.startsWith(UPLOADS_DIR)) {
    return res.status(403).send('Forbidden: Access denied.');
  }

  // Check if the file exists and is accessible before attempting to stream.
  fs.access(filePath, fs.constants.F_OK, (err) => {
    if (err) {
      // The file does not exist or is not accessible.
      return res.status(404).send('Not Found: The requested file does not exist.');
    }

    // Determine the Content-Type based on the file extension.
    // Default to a generic binary stream type if the type cannot be determined.
    const contentType = mime.lookup(filePath) || 'application/octet-stream';
    res.setHeader('Content-Type', contentType);

    const readStream = fs.createReadStream(filePath);

    // Handle potential errors during the stream (e.g., file deleted mid-stream).
    readStream.on('error', (streamError) => {
      console.error('Stream Error:', streamError);
      // If headers haven't been sent, we can send a proper error status.
      // Otherwise, we just terminate the connection.
      if (!res.headersSent) {
        res.status(500).send('Internal Server Error');
      } else {
        res.end();
      }
    });

    // Efficiently pipe the file stream directly to the HTTP response.
    readStream.pipe(res);
  });
});

app.listen(PORT, () => {
  console.log(`Server running on http://localhost:${PORT}`);
  console.log(`Place files in the "${UPLOADS_DIR}" directory.`);
  console.log(`Access them via: http://localhost:${PORT}/files?filename=yourfile.ext`);
});
