'use strict';

const express = require('express');
const { spawn } = require('child_process');

const app = express();

app.use(express.json({ limit: '1kb', strict: true, type: ['application/json', '*/json'] }));

const MAX_HOSTNAME_LENGTH = 255;
const PING_COUNT = 4;
const PING_TIMEOUT_MS = 10_000;

function isValidHostnameOrIp(value) {
  if (typeof value !== 'string') return false;
  const host = value.trim();

  if (!host || host.length > MAX_HOSTNAME_LENGTH) return false;
  if (/\s/.test(host)) return false;
  if (host.includes('\0')) return false;

  // Allow:
  // - DNS names: labels separated by dots (letters/digits/hyphen), no leading/trailing hyphen per label
  // - IPv4
  // - IPv6 (basic check)
  const isIPv4 = /^(?:\d{1,3}\.){3}\d{1,3}$/.test(host) && host.split('.').every(o => Number(o) >= 0 && Number(o) <= 255);
  const isIPv6 = /^[0-9a-fA-F:]{2,}$/.test(host) && host.includes(':') && !host.includes(':::')

  const isDnsName = /^(?=.{1,255}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)(?:\.(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?))*\.?$/.test(host);

  return isIPv4 || isIPv6 || isDnsName;
}

app.post('/api/ping', (req, res) => {
  const hostname = typeof req.body === 'object' && req.body ? req.body.hostname : undefined;

  if (!isValidHostnameOrIp(hostname)) {
    res.status(400).json({ error: 'Invalid hostname' });
    return;
  }

  const host = hostname.trim();
  const isWin = process.platform === 'win32';
  const args = isWin ? ['-n', String(PING_COUNT), host] : ['-c', String(PING_COUNT), host];

  const child = spawn('ping', args, { shell: false, windowsHide: true });

  let stdout = '';
  let stderr = '';
  let finished = false;

  const timer = setTimeout(() => {
    if (finished) return;
    finished = true;
    child.kill('SIGKILL');
    res.status(504).type('text/plain; charset=utf-8').send('Ping timed out');
  }, PING_TIMEOUT_MS);

  child.stdout.on('data', (chunk) => { stdout += chunk.toString('utf8'); });
  child.stderr.on('data', (chunk) => { stderr += chunk.toString('utf8'); });

  child.on('error', (err) => {
    if (finished) return;
    finished = true;
    clearTimeout(timer);
    res.status(500).type('text/plain; charset=utf-8').send(`Failed to start ping: ${err.message}`);
  });

  child.on('close', () => {
    if (finished) return;
    finished = true;
    clearTimeout(timer);
    res.status(200).type('text/plain; charset=utf-8').send(stdout + (stderr ? `\n${stderr}` : ''));
  });
});

module.exports = app;

// If running directly: node server.js
if (require.main === module) {
  const port = Number(process.env.PORT) || 3000;
  app.listen(port, () => {
    // eslint-disable-next-line no-console
    console.log(`Listening on http://localhost:${port}`);
  });
}
