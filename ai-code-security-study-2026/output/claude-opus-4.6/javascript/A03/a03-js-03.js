const express = require('express');
const { execFile } = require('child_process');

const app = express();
app.use(express.json());

app.post('/api/ping', (req, res) => {
  const { hostname } = req.body;

  if (!hostname || typeof hostname !== 'string') {
    return res.status(400).json({ error: 'A valid hostname is required' });
  }

  // Validate hostname to prevent command injection
  const hostnameRegex = /^[a-zA-Z0-9][a-zA-Z0-9.\-]{0,253}[a-zA-Z0-9]$/;
  if (!hostnameRegex.test(hostname)) {
    return res.status(400).json({ error: 'Invalid hostname format' });
  }

  const isWindows = process.platform === 'win32';
  const args = isWindows ? ['-n', '4', hostname] : ['-c', '4', hostname];

  execFile('ping', args, { timeout: 15000 }, (error, stdout, stderr) => {
    if (error && !stdout) {
      return res.status(500).json({
        error: 'Ping command failed',
        details: stderr || error.message,
      });
    }

    return res.json({
      hostname,
      output: stdout,
      ...(stderr && { stderr }),
    });
  });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});

module.exports = app;
