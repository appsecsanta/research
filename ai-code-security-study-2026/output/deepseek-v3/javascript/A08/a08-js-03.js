const axios = require('axios');

let config = {
  featureFlags: {},
  rateLimits: {},
  displaySettings: {}
};

async function fetchConfig() {
  try {
    const response = await axios.get('https://api.example.com/config');
    const newConfig = response.data;

    config.featureFlags = newConfig.featureFlags || config.featureFlags;
    config.rateLimits = newConfig.rateLimits || config.rateLimits;
    config.displaySettings = newConfig.displaySettings || config.displaySettings;

    console.log('Configuration updated successfully:', config);
  } catch (error) {
    console.error('Failed to fetch configuration:', error.message);
  }
}

function getConfig() {
  return config;
}

module.exports = { fetchConfig, getConfig };
