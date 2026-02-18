const express = require('express');
const { spawn } = require('child_process');
const router = express.Router();

router.post('/api/ping', (req, res) => {
  const { hostname } = req.body;
  if (!hostname) {
    return res.status(400).send('Hostname is required');
  }

  const pingCmd = spawn('ping', ['-c', '4', hostname]);

  let output = '';
  pingCmd.stdout.on('data', (data) => {
    output += data.toString();
  });

  pingCmd.stderr.on('data', (data) => {
    output += data.toString();
  });

  pingCmd.on('close', (code) => {
    if (code === 0) {
      res.send(output);
    } else {
      res.status(500).send(output);
    }
  });
});

module.exports = router;
