const express = require('express');
const { spawn } = require('child_process');

const app = express();
app.use(express.json());

app.post('/api/ping', (req, res) => {
  const { hostname } = req.body;
  if (!hostname || typeof hostname !== 'string') {
    return res.status(400).json({ error: 'Valid hostname is required' });
  }

  // Basic validation for hostname (alphanumeric, dots, hyphens)
  if (!/^[a-zA-Z0-9.-]+$/.test(hostname)) {
    return res.status(400).json({ error: 'Invalid hostname' });
  }

  const pingProcess = spawn('ping', ['-c', '4', hostname]);

  let output = '';
  pingProcess.stdout.on('data', (data) => {
    output += data.toString();
  });

  pingProcess.stderr.on('data', (data) => {
    output += data.toString();
  });

  pingProcess.on('close', (code) => {
    if (code !== 0) {
      return res.status(500).json({ error: 'Ping failed', output });
    }
    res.json({ output });
  });
});

// For demonstration; in production, export the app or integrate accordingly
// app.listen(3000, () => console.log('Server running on port 3000'));
