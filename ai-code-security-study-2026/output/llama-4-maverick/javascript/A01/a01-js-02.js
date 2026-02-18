const express = require('express');
const fs = require('fs');
const path = require('path');
const mime = require('mime-types');

const router = express.Router();

router.get('/download', (req, res) => {
  const filename = req.query.filename;
  if (!filename) {
    return res.status(400).send('Filename is required');
  }

  const filePath = path.join(__dirname, 'uploads', filename);
  if (!fs.existsSync(filePath)) {
    return res.status(404).send('File not found');
  }

  const mimeType = mime.lookup(filePath);
  if (mimeType) {
    res.set("Content-Type", mimeType);
  }

  const fileStream = fs.createReadStream(filePath);
  fileStream.pipe(res);

  fileStream.on('error', (err) => {
    console.error(err);
    res.status(500).send('Error reading file');
  });
});

module.exports = router;
