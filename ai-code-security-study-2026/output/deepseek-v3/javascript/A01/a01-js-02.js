const express = require('express');
const fs = require('fs');
const path = require('path');
const mime = require('mime-types');

const app = express();
const uploadsDir = path.join(__dirname, 'uploads');

app.get('/file', (req, res) => {
    const filename = req.query.filename;
    if (!filename) {
        return res.status(400).send('Filename is required');
    }

    const filePath = path.join(uploadsDir, filename);
    if (!fs.existsSync(filePath)) {
        return res.status(404).send('File not found');
    }

    const contentType = mime.lookup(filename) || 'application/octet-stream';
    res.setHeader('Content-Type', contentType);

    const readStream = fs.createReadStream(filePath);
    readStream.pipe(res);
});

const PORT = 3000;
app.listen(PORT, () => {
    console.log(`Server is running on port ${PORT}`);
});
