import axios from 'axios';
import logger from './logger.js';

const CONFIG_URL = 'https://example.com/config.json';

const fetchConfig = async () => {
  try {
    const response = await axios.get(CONFIG_URL);
    return response.data;
  } catch (error) {
    logger.error(`Failed to fetch config: ${error.message}`);
    throw error;
  }
};

const applyConfig = (config) => {
  if (!config) return;

  const { featureFlags, rateLimits, displaySettings } = config;

  // Apply feature flags
  Object.keys(featureFlags).forEach((flag) => {
    process.env[`FEATURE_${flag.toUpperCase()}`] = featureFlags[flag].toString();
  });

  // Apply rate limits
  Object.keys(rateLimits).forEach((limit) => {
    global.rateLimits[limit] = rateLimits[limit];
  });

  // Apply display settings
  Object.keys(displaySettings).forEach((setting) => {
    global.displaySettings[setting] = displaySettings[setting];
  });
};

const updateConfig = async () => {
  try {
    const config = await fetchConfig();
    applyConfig(config);
    logger.info('Config updated successfully');
  } catch (error) {
    logger.error(`Failed to update config: ${error.message}`);
  }
};

export default updateConfig;
