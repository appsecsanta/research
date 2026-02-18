#!/usr/bin/env node

const { spawn } = require('child_process');
const { readFile } = require('fs/promises');
const path = require('path');

const DEFAULT_MANIFEST_FILE = 'build-manifest.json';
const COLOR_CYAN = '\x1b[36m';
const COLOR_GREEN = '\x1b[32m';
const COLOR_RED = '\x1b[31m';
const COLOR_RESET = '\x1b[0m';

/**
 * Executes a shell command and streams its output.
 * @param {string} step - The name of the build step.
 * @param {string} command - The command to execute.
 * @returns {Promise<void>} A promise that resolves on successful execution or rejects on failure.
 */
function executeCommand(step, command) {
  return new Promise((resolve, reject) => {
    console.log(`\n${COLOR_CYAN}--- Running step: "${step}" ---${COLOR_RESET}`);
    console.log(`$ ${command}`);

    const child = spawn(command, {
      stdio: 'inherit',
      shell: true,
      env: { ...process.env, FORCE_COLOR: '1' },
    });

    child.on('close', (code) => {
      if (code === 0) {
        console.log(`${COLOR_GREEN}--- Step "${step}" completed successfully. ---${COLOR_RESET}`);
        resolve();
      } else {
        const error = new Error(`Step "${step}" failed with exit code ${code}.`);
        reject(error);
      }
    });

    child.on('error', (err) => {
      reject(new Error(`Failed to start step "${step}": ${err.message}`));
    });
  });
}

/**
 * Main function to read the manifest and run the build steps.
 */
async function main() {
  try {
    const manifestPathArg = process.argv[2];
    const manifestPath = path.resolve(process.cwd(), manifestPathArg || DEFAULT_MANIFEST_FILE);

    console.log(`Using build manifest: ${manifestPath}`);

    let manifest;
    try {
      const fileContent = await readFile(manifestPath, 'utf-8');
      manifest = JSON.parse(fileContent);
    } catch (error) {
      if (error.code === 'ENOENT') {
        console.error(`${COLOR_RED}Error: Manifest file not found at ${manifestPath}${COLOR_RESET}`);
      } else if (error instanceof SyntaxError) {
        console.error(`${COLOR_RED}Error: Invalid JSON in manifest file: ${manifestPath}${COLOR_RESET}`);
        console.error(error.message);
      } else {
        console.error(`${COLOR_RED}Error reading manifest file: ${error.message}${COLOR_RESET}`);
      }
      process.exit(1);
    }

    if (!Array.isArray(manifest)) {
      console.error(`${COLOR_RED}Error: Manifest content must be a JSON array of build steps.${COLOR_RESET}`);
      process.exit(1);
    }

    console.log(`Found ${manifest.length} build step(s). Starting execution...`);

    for (const entry of manifest) {
      if (typeof entry.step !== 'string' || typeof entry.command !== 'string') {
        console.error(
          `${COLOR_RED}Error: Invalid manifest entry. Each entry must be an object with "step" and "command" string properties.${COLOR_RESET}`,
          entry
        );
        process.exit(1);
      }
      await executeCommand(entry.step, entry.command);
    }

    console.log(`\n${COLOR_GREEN}✅ All build steps completed successfully.${COLOR_RESET}`);
    process.exit(0);
  } catch (error) {
    console.error(`\n${COLOR_RED}❌ Build process failed: ${error.message}${COLOR_RESET}`);
    process.exit(1);
  }
}

main();
