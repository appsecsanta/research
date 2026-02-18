const http = require('http');
const https = require('https');
const { EventEmitter } = require('events');

class ConfigManager extends EventEmitter {
  constructor(options = {}) {
    super();
    this.endpoint = options.endpoint || 'https://api.example.com/config';
    this.pollInterval = options.pollInterval || 60000;
    this.timeout = options.timeout || 5000;
    this.retryAttempts = options.retryAttempts || 3;
    this.retryDelay = options.retryDelay || 2000;
    this.headers = options.headers || {};

    this.config = {
      featureFlags: {},
      rateLimits: {},
      displaySettings: {},
    };

    this._pollTimer = null;
    this._lastEtag = null;
    this._lastModified = null;
    this._initialized = false;
  }

  async initialize() {
    try {
      await this._fetchAndApply();
      this._initialized = true;
      this._startPolling();
      this.emit('initialized', this.config);
      return this.config;
    } catch (error) {
      this.emit('error', new Error(`Failed to initialize config: ${error.message}`));
      throw error;
    }
  }

  async _fetchAndApply() {
    const rawConfig = await this._fetchWithRetry();
    if (rawConfig === null) {
      // Not modified (304), keep current config
      return this.config;
    }
    const validated = this._validateConfig(rawConfig);
    const previous = { ...this.config };
    this._applyConfig(validated);
    this._emitChanges(previous, this.config);
    return this.config;
  }

  _fetchRemoteConfig() {
    return new Promise((resolve, reject) => {
      const url = new URL(this.endpoint);
      const client = url.protocol === 'https:' ? https : http;

      const headers = {
        'Accept': 'application/json',
        ...this.headers,
      };

      if (this._lastEtag) {
        headers['If-None-Match'] = this._lastEtag;
      }
      if (this._lastModified) {
        headers['If-Modified-Since'] = this._lastModified;
      }

      const requestOptions = {
        hostname: url.hostname,
        port: url.port,
        path: url.pathname + url.search,
        method: 'GET',
        headers,
        timeout: this.timeout,
      };

      const req = client.request(requestOptions, (res) => {
        if (res.statusCode === 304) {
          resolve(null);
          return;
        }

        if (res.statusCode < 200 || res.statusCode >= 300) {
          reject(new Error(`HTTP ${res.statusCode}: ${res.statusMessage}`));
          return;
        }

        if (res.headers['etag']) {
          this._lastEtag = res.headers['etag'];
        }
        if (res.headers['last-modified']) {
          this._lastModified = res.headers['last-modified'];
        }

        let body = '';
        res.setEncoding('utf8');
        res.on('data', (chunk) => {
          body += chunk;
        });
        res.on('end', () => {
          try {
            const parsed = JSON.parse(body);
            resolve(parsed);
          } catch (parseError) {
            reject(new Error(`Failed to parse config JSON: ${parseError.message}`));
          }
        });
      });

      req.on('timeout', () => {
        req.destroy();
        reject(new Error(`Request timed out after ${this.timeout}ms`));
      });

      req.on('error', (error) => {
        reject(new Error(`Network error: ${error.message}`));
      });

      req.end();
    });
  }

  async _fetchWithRetry() {
    let lastError;

    for (let attempt = 1; attempt <= this.retryAttempts; attempt++) {
      try {
        return await this._fetchRemoteConfig();
      } catch (error) {
        lastError = error;
        this.emit('retrying', { attempt, maxAttempts: this.retryAttempts, error });

        if (attempt < this.retryAttempts) {
          await this._sleep(this.retryDelay * attempt);
        }
      }
    }

    throw lastError;
  }

  _validateConfig(raw) {
    if (typeof raw !== 'object' || raw === null) {
      throw new Error('Config must be a non-null object');
    }

    const validated = {
      featureFlags: {},
      rateLimits: {},
      displaySettings: {},
    };

    // Validate feature flags
    if (raw.featureFlags && typeof raw.featureFlags === 'object') {
      for (const [key, value] of Object.entries(raw.featureFlags)) {
        if (typeof value === 'boolean') {
          validated.featureFlags[key] = value;
        } else if (typeof value === 'object' && value !== null) {
          // Support complex feature flags with rollout percentages, user targeting, etc.
          validated.featureFlags[key] = this._validateFeatureFlag(key, value);
        } else {
          this.emit('warning', `Invalid feature flag value for "${key}", skipping`);
        }
      }
    }

    // Validate rate limits
    if (raw.rateLimits && typeof raw.rateLimits === 'object') {
      for (const [key, value] of Object.entries(raw.rateLimits)) {
        if (typeof value === 'object' && value !== null) {
          const rateLimit = this._validateRateLimit(key, value);
          if (rateLimit) {
            validated.rateLimits[key] = rateLimit;
          }
        } else {
          this.emit('warning', `Invalid rate limit config for "${key}", skipping`);
        }
      }
    }

    // Validate display settings
    if (raw.displaySettings && typeof raw.displaySettings === 'object') {
      for (const [key, value] of Object.entries(raw.displaySettings)) {
        validated.displaySettings[key] = this._validateDisplaySetting(key, value);
      }
    }

    return validated;
  }

  _validateFeatureFlag(key, value) {
    const flag = {
      enabled: Boolean(value.enabled),
    };

    if (typeof value.rolloutPercentage === 'number') {
      flag.rolloutPercentage = Math.max(0, Math.min(100, value.rolloutPercentage));
    }

    if (Array.isArray(value.allowedUsers)) {
      flag.allowedUsers = value.allowedUsers.filter((u) => typeof u === 'string');
    }

    if (Array.isArray(value.allowedGroups)) {
      flag.allowedGroups = value.allowedGroups.filter((g) => typeof g === 'string');
    }

    if (typeof value.description === 'string') {
      flag.description = value.description;
    }

    return flag;
  }

  _validateRateLimit(key, value) {
    const maxRequests = parseInt(value.maxRequests, 10);
    const windowMs = parseInt(value.windowMs, 10);

    if (isNaN(maxRequests) || maxRequests <= 0) {
      this.emit('warning', `Invalid maxRequests for rate limit "${key}", skipping`);
      return null;
    }

    if (isNaN(windowMs) || windowMs <= 0) {
      this.emit('warning', `Invalid windowMs for rate limit "${key}", skipping`);
      return null;
    }

    return {
      maxRequests,
      windowMs,
      burstLimit: typeof value.burstLimit === 'number' ? Math.max(0, value.burstLimit) : undefined,
      skipFailedRequests: Boolean(value.skipFailedRequests),
      keyGenerator: typeof value.keyGenerator === 'string' ? value.keyGenerator : 'ip',
    };
  }

  _validateDisplaySetting(key, value) {
    // Allow primitives and plain objects/arrays
    if (value === null || value === undefined) {
      return null;
    }
    if (['string', 'number', 'boolean'].includes(typeof value)) {
      return value;
    }
    if (Array.isArray(value)) {
      return [...value];
    }
    if (typeof value === 'object') {
      return JSON.parse(JSON.stringify(value));
    }
    return String(value);
  }

  _applyConfig(validated) {
    this.config = {
      featureFlags: { ...validated.featureFlags },
      rateLimits: { ...validated.rateLimits },
      displaySettings: { ...validated.displaySettings },
      _appliedAt: new Date().toISOString(),
    };
  }

  _emitChanges(previous, current) {
    const changes = [];

    // Check feature flag changes
    const allFlagKeys = new Set([
      ...Object.keys(previous.featureFlags || {}),
      ...Object.keys(current.featureFlags || {}),
    ]);

    for (const key of allFlagKeys) {
      const prev = previous.featureFlags?.[key];
      const curr = current.featureFlags?.[key];
      if (JSON.stringify(prev) !== JSON.stringify(curr)) {
        changes.push({ type: 'featureFlag', key, previous: prev, current: curr });
      }
    }

    // Check rate limit changes
    const allRateLimitKeys = new Set([
      ...Object.keys(previous.rateLimits || {}),
      ...Object.keys(current.rateLimits || {}),
    ]);

    for (const key of allRateLimitKeys) {
      const prev = previous.rateLimits?.[key];
      const curr = current.rateLimits?.[key];
      if (JSON.stringify(prev) !== JSON.stringify(curr)) {
        changes.push({ type: 'rateLimit', key, previous: prev, current: curr });
      }
    }

    // Check display setting changes
    const allDisplayKeys = new Set([
      ...Object.keys(previous.displaySettings || {}),
      ...Object.keys(current.displaySettings || {}),
    ]);

    for (const key of allDisplayKeys) {
      const prev = previous.displaySettings?.[key];
      const curr = current.displaySettings?.[key];
      if (JSON.stringify(prev) !== JSON.stringify(curr)) {
        changes.push({ type: 'displaySetting', key, previous: prev, current: curr });
      }
    }

    if (changes.length > 0) {
      this.emit('configChanged', { changes, config: current });
    }
  }

  _startPolling() {
    this.stopPolling();
    this._pollTimer = setInterval(async () => {
      try {
        await this._fetchAndApply();
        this.emit('refreshed', this.config);
      } catch (error) {
        this.emit('refreshError', error);
        // Keep using the last known good config
      }
    }, this.pollInterval);

    // Allow the process to exit even if the timer is running
    if (this._pollTimer.unref) {
      this._pollTimer.unref();
    }
  }

  stopPolling() {
    if (this._pollTimer) {
      clearInterval(this._pollTimer);
      this._pollTimer = null;
    }
  }

  async forceRefresh() {
    this._lastEtag = null;
    this._lastModified = null;
    return this._fetchAndApply();
  }

  // Feature flag accessors
  isFeatureEnabled(flagName, context = {}) {
    const flag = this.config.featureFlags[flagName];

    if (flag === undefined) {
      return false;
    }

    if (typeof flag === 'boolean') {
      return flag;
    }

    if (!flag.enabled) {
      return false;
    }

    // Check user-level targeting
    if (flag.allowedUsers && context.userId) {
      if (flag.allowedUsers.includes(context.userId)) {
        return true;
      }
    }

    // Check group-level targeting
    if (flag.allowedGroups && context.userGroup) {
      if (flag.allowedGroups.includes(context.userGroup)) {
        return true;
      }
    }

    // Check rollout percentage
    if (typeof flag.rolloutPercentage === 'number' && context.userId) {
      const hash = this._hashString(`${flagName}:${context.userId}`);
      const bucket = hash % 100;
      return bucket < flag.rolloutPercentage;
    }

    // If no targeting rules matched but flag is enabled, return true
    if (!flag.allowedUsers && !flag.allowedGroups && typeof flag.rolloutPercentage !== 'number') {
      return true;
    }

    return false;
  }

  getRateLimit(key) {
    return this.config.rateLimits[key] || null;
  }

  getDisplaySetting(key, defaultValue = null) {
    const value = this.config.displaySettings[key];
    return value !== undefined ? value : defaultValue;
  }

  getConfig() {
    return JSON.parse(JSON.stringify(this.config));
  }

  _hashString(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash; // Convert to 32-bit integer
    }
    return Math.abs(hash);
  }

  _sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  destroy() {
    this.stopPolling();
    this.removeAllListeners();
  }
}

// Rate limiter middleware that uses ConfigManager
function createRateLimiter(configManager) {
  const buckets = new Map();

  return function rateLimiterMiddleware(limitKey) {
    return (req, res, next) => {
      const limitConfig = configManager.getRateLimit(limitKey);

      if (!limitConfig) {
        return next();
      }

      const { maxRequests, windowMs, burstLimit, skipFailedRequests, keyGenerator } = limitConfig;

      let clientKey;
      if (keyGenerator === 'ip') {
        clientKey = req.ip || req.connection?.remoteAddress || 'unknown';
      } else if (keyGenerator === 'user') {
        clientKey = req.user?.id || req.ip || 'unknown';
      } else {
        clientKey = req.ip || 'unknown';
      }

      const bucketKey = `${limitKey}:${clientKey}`;
      const now = Date.now();

      if (!buckets.has(bucketKey)) {
        buckets.set(bucketKey, { tokens: maxRequests, lastRefill: now });
      }

      const bucket = buckets.get(bucketKey);

      // Refill tokens based on elapsed time
      const elapsed = now - bucket.lastRefill;
      const refillRate = maxRequests / windowMs;
      const tokensToAdd = elapsed * refillRate;
      const maxTokens = burstLimit || maxRequests;
      bucket.tokens = Math.min(maxTokens, bucket.tokens + tokensToAdd);
      bucket.lastRefill = now;

      if (bucket.tokens >= 1) {
        bucket.tokens -= 1;

        res.setHeader('X-RateLimit-Limit', maxRequests);
        res.setHeader('X-RateLimit-Remaining', Math.floor(bucket.tokens));
        res.setHeader('X-RateLimit-Reset', new Date(now + windowMs).toISOString());

        if (skipFailedRequests) {
          const originalEnd = res.end.bind(res);
          res.end = function (...args) {
            if (res.statusCode >= 400) {
              bucket.tokens += 1;
            }
            return originalEnd(...args);
          };
        }

        return next();
      }

      res.setHeader('X-RateLimit-Limit', maxRequests);
      res.setHeader('X-RateLimit-Remaining', 0);
      res.setHeader('X-RateLimit-Reset', new Date(now + windowMs).toISOString());
      res.setHeader('Retry-After', Math.ceil(windowMs / 1000));
      res.statusCode = 429;
      res.end(JSON.stringify({ error: 'Too Many Requests' }));
    };
  };
}

// Express middleware for injecting config into requests
function configMiddleware(configManager) {
  return (req, res, next) => {
    req.config = configManager;
    req.isFeatureEnabled = (flag) => {
      return configManager.isFeatureEnabled(flag, {
        userId: req.user?.id,
        userGroup: req.user?.group,
      });
    };
    req.getDisplaySetting = (key, defaultValue) => {
      return configManager.getDisplaySetting(key, defaultValue);
    };
    next();
  };
}

module.exports = {
  ConfigManager,
  createRateLimiter,
  configMiddleware,
};

// Usage example
if (require.main === module) {
  (async () => {
    const configManager = new ConfigManager({
      endpoint: 'https://api.example.com/config',
      pollInterval: 30000,
      timeout: 5000,
      retryAttempts: 3,
      headers: {
        'Authorization': `Bearer ${process.env.CONFIG_API_KEY || 'test-key'}`,
      },
    });

    configManager.on('initialized', (config) => {
      console.log('Config initialized:', JSON.stringify(config, null, 2));
    });

    configManager.on('configChanged', ({ changes, config }) => {
      console.log('Config changed:', changes);
    });

    configManager.on('refreshError', (error) => {
      console.error('Config refresh failed:', error.message);
    });

    configManager.on('warning', (message) => {
      console.warn('Config warning:', message);
    });

    try {
      await configManager.initialize();

      // Check feature flags
      const isDarkMode = configManager.isFeatureEnabled('darkMode', { userId: 'user-123' });
      console.log('Dark mode enabled:', isDarkMode);

      // Get rate limit config
      const apiLimit = configManager.getRateLimit('api');
      console.log('API rate limit:', apiLimit);

      // Get display settings
      const theme = configManager.getDisplaySetting('theme', 'default');
      console.log('Theme:', theme);
    } catch (error) {
      console.error('Failed to start:', error.message);
    }

    // Graceful shutdown
    process.on('SIGTERM', () => {
      configManager.destroy();
      process.exit(0);
    });
  })();
}
