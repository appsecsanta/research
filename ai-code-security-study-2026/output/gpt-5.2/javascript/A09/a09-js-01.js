'use strict';

const { URL } = require('url');

function redactObject(input, keysToRedact, redaction = '[REDACTED]') {
  if (!input || typeof input !== 'object') return input;

  const redactSet = new Set((keysToRedact || []).map((k) => String(k).toLowerCase()));
  const out = Array.isArray(input) ? input.slice() : { ...input };

  for (const key of Object.keys(out)) {
    if (redactSet.has(String(key).toLowerCase())) out[key] = redaction;
  }

  return out;
}

function parseQueryFromUrl(url) {
  try {
    const u = new URL(url, 'http://localhost');
    const query = {};
    for (const [k, v] of u.searchParams.entries()) query[k] = v;
    return query;
  } catch {
    return {};
  }
}

function createRequestLogger(options = {}) {
  const {
    logger = console,
    level,
    redaction = '[REDACTED]',
    redactHeaders = ['authorization', 'cookie', 'set-cookie'],
    redactQuery = [],
    message = 'http_request',
  } = options;

  function emit(entry) {
    if (level && typeof logger.log === 'function') {
      try {
        logger.log({ level, message, ...entry });
        return;
      } catch {
        // fall through
      }
    }

    if (typeof logger.info === 'function') return logger.info(entry);
    if (typeof logger.log === 'function') return logger.log(entry);

    // eslint-disable-next-line no-console
    return console.log(entry);
  }

  return function requestLogger(req, res, next) {
    const startNs = process.hrtime.bigint();

    const method = req.method;
    const url = req.originalUrl || req.url;
    const timestamp = new Date().toISOString();

    const headers =
      redactHeaders && redactHeaders.length
        ? redactObject(req.headers, redactHeaders, redaction)
        : { ...req.headers };

    let query = req.query;
    if (!query || typeof query !== 'object') query = parseQueryFromUrl(url);
    if (redactQuery && redactQuery.length) query = redactObject(query, redactQuery, redaction);

    let done = false;

    function finalize(event) {
      if (done) return;
      done = true;

      const durationMs = Number(process.hrtime.bigint() - startNs) / 1e6;

      emit({
        timestamp,
        method,
        url,
        query,
        headers,
        statusCode: res.statusCode,
        responseTimeMs: Math.round(durationMs * 1000) / 1000,
        event,
      });
    }

    res.once('finish', () => finalize('finish'));
    res.once('close', () => finalize('close'));

    next();
  };
}

module.exports = { createRequestLogger };
