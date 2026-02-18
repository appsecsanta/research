'use strict';

const express = require('express');
const puppeteer = require('puppeteer');

const app = express();
app.use(express.json({ limit: '1mb' }));

let browserPromise;

function getBrowser() {
  if (!browserPromise) {
    browserPromise = puppeteer.launch({
      headless: 'new',
      args: ['--no-sandbox', '--disable-setuid-sandbox'],
    });
  }
  return browserPromise;
}

function isAllowedUrl(raw) {
  let u;
  try {
    u = new URL(raw);
  } catch {
    return false;
  }
  if (!['http:', 'https:'].includes(u.protocol)) return false;

  // Basic SSRF hardening (block localhost / private ranges)
  const host = u.hostname.toLowerCase();
  if (host === 'localhost' || host === '127.0.0.1' || host === '::1') return false;

  // Block obvious private-network hostnames (best-effort; DNS can still resolve to private IPs)
  if (
    host.endsWith('.local') ||
    host.endsWith('.internal') ||
    host.endsWith('.lan')
  ) {
    return false;
  }

  return true;
}

function safeFilenameFromUrl(raw) {
  let u;
  try {
    u = new URL(raw);
  } catch {
    return 'export.pdf';
  }

  const base =
    (u.pathname && u.pathname !== '/' ? u.pathname.split('/').filter(Boolean).pop() : '') ||
    u.hostname ||
    'export';

  const name = String(base)
    .replace(/\.[a-z0-9]+$/i, '')
    .replace(/[^a-z0-9-_]+/gi, '-')
    .replace(/-+/g, '-')
    .replace(/^[-_]+|[-_]+$/g, '')
    .slice(0, 80) || 'export';

  return `${name}.pdf`;
}

app.post('/api/export-pdf', async (req, res) => {
  const url = req.body && typeof req.body.url === 'string' ? req.body.url.trim() : '';

  if (!url) {
    return res.status(400).json({ error: 'Missing "url" in request body.' });
  }
  if (!isAllowedUrl(url)) {
    return res.status(400).json({ error: 'Invalid or disallowed URL.' });
  }

  let page;
  try {
    const browser = await getBrowser();
    page = await browser.newPage();

    await page.setViewport({ width: 1280, height: 720, deviceScaleFactor: 1 });
    await page.setUserAgent(
      'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome Safari/537.36'
    );

    await page.goto(url, { waitUntil: 'networkidle2', timeout: 45000 });
    await page.emulateMediaType('screen');

    const pdfBuffer = await page.pdf({
      format: 'A4',
      printBackground: true,
      preferCSSPageSize: true,
      margin: { top: '12mm', right: '12mm', bottom: '12mm', left: '12mm' },
      timeout: 45000,
    });

    const filename = safeFilenameFromUrl(url);

    res.status(200);
    res.setHeader('Content-Type', 'application/pdf');
    res.setHeader('Content-Length', String(pdfBuffer.length));
    res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
    res.end(pdfBuffer);
  } catch (err) {
    const message = err && err.message ? err.message : 'Failed to generate PDF.';
    res.status(500).json({ error: message });
  } finally {
    if (page) {
      try {
        await page.close();
      } catch {}
    }
  }
});

process.on('SIGINT', async () => {
  try {
    const browser = await browserPromise;
    if (browser) await browser.close();
  } catch {}
  process.exit(0);
});

process.on('SIGTERM', async () => {
  try {
    const browser = await browserPromise;
    if (browser) await browser.close();
  } catch {}
  process.exit(0);
});

const PORT = Number(process.env.PORT) || 3000;
app.listen(PORT, () => {
  // eslint-disable-next-line no-console
  console.log(`Server listening on port ${PORT}`);
});
