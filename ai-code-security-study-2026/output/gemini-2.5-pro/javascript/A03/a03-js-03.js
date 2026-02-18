const express = require('express');
const { execFile } = require('child_process');
const os = require('os');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());

app.post('/api/ping', (req, res) => {
  const { hostname } = req.body;

  if (!hostname) {
    return res.status(400).json({
      error: 'Hostname is required in the request body.'
    });
  }

  // Basic validation to prevent command injection characters,
  // even though execFile is inherently safer than exec.
  const HOSTNAME_REGEX = /^([a-zA-Z0-9.-]+)$/;
  if (!HOSTNAME_REGEX.test(hostname)) {
    return res.status(400).json({
      error: 'Invalid hostname format.'
    });
  }

  // Determine platform-specific arguments to limit the ping count.
  const pingCountArg = os.platform() === 'win32' ? '-n' : '-c';
  const pingArgs = [pingCountArg, '4', hostname];

  execFile('ping', pingArgs, (error, stdout, stderr) => {
    // The 'ping' command exits with a non-zero status code if the host is
    // unreachable. This is a valid, expected outcome, not a server error.
    // We return a 200 OK with a structured response indicating the result.
    if (error) {
      return res.status(200).json({
        success: false,
        hostname,
        message: `Host ${hostname} may be unreachable or an error occurred.`,
        output: stdout,
        error: stderr,
        code: error.code,
      });
    }

    res.status(200).json({
      success: true,
      hostname,
      output: stdout,
      error: stderr, // stderr might contain warnings even on success
    });
  });
});

app.listen(PORT, () => {
  console.log(`Ping service listening on http://localhost:${PORT}`);
});

module.exports = app;
