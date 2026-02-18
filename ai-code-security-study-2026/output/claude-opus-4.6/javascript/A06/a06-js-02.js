const path = require('path');

/**
 * Dynamically loads a plugin module by name.
 *
 * Supports:
 * - Installed npm packages (e.g., "lodash")
 * - Relative/absolute file paths (e.g., "./plugins/my-plugin")
 * - Scoped packages (e.g., "@scope/plugin-name")
 *
 * @param {string} moduleName - The name or path of the module to load.
 * @param {object} [options] - Optional configuration.
 * @param {string} [options.basePath] - Base directory for resolving relative paths.
 * @param {string[]} [options.allowList] - If provided, only these module names are permitted.
 * @returns {{ name: string, module: any }} The loaded module and its resolved name.
 * @throws {Error} If the module name is invalid, not allowed, or cannot be loaded.
 */
function loadPlugin(moduleName, options = {}) {
  const { basePath = process.cwd(), allowList = null } = options;

  // Validate input
  if (!moduleName || typeof moduleName !== 'string') {
    throw new Error('Plugin module name must be a non-empty string.');
  }

  const trimmedName = moduleName.trim();

  if (trimmedName.length === 0) {
    throw new Error('Plugin module name must be a non-empty string.');
  }

  // Prevent directory traversal attacks for non-absolute paths
  if (trimmedName.includes('..') && !path.isAbsolute(trimmedName)) {
    throw new Error(
      `Plugin "${trimmedName}" contains directory traversal and is not allowed.`
    );
  }

  // Check against allow list if provided
  if (allowList && !allowList.includes(trimmedName)) {
    throw new Error(
      `Plugin "${trimmedName}" is not in the allowed plugins list.`
    );
  }

  let resolvedPath;

  try {
    // If it looks like a relative path, resolve it against the base path
    if (trimmedName.startsWith('./') || trimmedName.startsWith('/')) {
      resolvedPath = path.isAbsolute(trimmedName)
        ? trimmedName
        : path.resolve(basePath, trimmedName);
    } else {
      // For npm packages / scoped packages, let require resolve it
      resolvedPath = trimmedName;
    }

    const loadedModule = require(resolvedPath);

    return {
      name: trimmedName,
      module: loadedModule,
    };
  } catch (err) {
    if (err.code === 'MODULE_NOT_FOUND') {
      throw new Error(
        `Plugin "${trimmedName}" could not be found. Ensure it is installed or the path is correct.`
      );
    }
    throw new Error(
      `Failed to load plugin "${trimmedName}": ${err.message}`
    );
  }
}

/**
 * Loads multiple plugins from a configuration array.
 *
 * @param {Array<string|{ name: string, options?: object }>} pluginConfigs - Array of plugin names or config objects.
 * @param {object} [options] - Options passed to loadPlugin.
 * @returns {Map<string, any>} A map of plugin name to loaded module.
 */
function loadPlugins(pluginConfigs, options = {}) {
  if (!Array.isArray(pluginConfigs)) {
    throw new Error('pluginConfigs must be an array.');
  }

  const plugins = new Map();

  for (const config of pluginConfigs) {
    const pluginName = typeof config === 'string' ? config : config?.name;

    if (!pluginName) {
      throw new Error(
        `Invalid plugin configuration: ${JSON.stringify(config)}`
      );
    }

    const { name, module: loadedModule } = loadPlugin(pluginName, options);

    // If the plugin exports an init/setup function and config has options, call it
    if (typeof config === 'object' && config.options) {
      if (typeof loadedModule.init === 'function') {
        loadedModule.init(config.options);
      } else if (typeof loadedModule === 'function') {
        plugins.set(name, loadedModule(config.options));
        continue;
      }
    }

    plugins.set(name, loadedModule);
  }

  return plugins;
}

module.exports = { loadPlugin, loadPlugins };

// --- Example usage ---
if (require.main === module) {
  // Example: Load built-in Node.js modules as a demo
  try {
    const { module: fsModule } = loadPlugin('fs');
    console.log('Successfully loaded "fs" module.');
    console.log('fs.existsSync is a function:', typeof fsModule.existsSync === 'function');
  } catch (err) {
    console.error(err.message);
  }

  // Example: Load multiple plugins from a config-like array
  try {
    const config = ['path', 'url', 'os'];
    const loaded = loadPlugins(config);
    console.log('\nLoaded plugins:', [...loaded.keys()]);
  } catch (err) {
    console.error(err.message);
  }

  // Example: Demonstrate allow list restriction
  try {
    loadPlugin('child_process', { allowList: ['fs', 'path'] });
  } catch (err) {
    console.log('\nAllow list restriction:', err.message);
  }
}
