/**
 * Dynamically loads a Node.js module by its name or path.
 * Returns the loaded module, or null if an error occurs.
 *
 * @param {string} moduleName - The name or path of the module to load (e.g., 'lodash', './my-plugin.js').
 * @returns {any | null} The exported module content, or null if loading fails.
 */
const loadModule = (moduleName) => {
  if (typeof moduleName !== 'string' || !moduleName.trim()) {
    console.error('[ModuleLoader] Error: Invalid module name provided. Must be a non-empty string.');
    return null;
  }

  try {
    // The require function resolves the module path and loads it.
    // Using a variable makes the loading dynamic.
    const loadedModule = require(moduleName);
    return loadedModule;
  } catch (error) {
    if (error.code === 'MODULE_NOT_FOUND') {
      console.error(`[ModuleLoader] Error: Could not find module '${moduleName}'. Please ensure it is installed or the path is correct.`);
    } else {
      // Catches other errors that might occur during module initialization.
      console.error(`[ModuleLoader] Error loading module '${moduleName}':`, error);
    }
    return null;
  }
};

module.exports = loadModule;
