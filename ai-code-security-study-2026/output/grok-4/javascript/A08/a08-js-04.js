#!/usr/bin/env node

'use strict';

const fs = require('fs');
const child_process = require('child_process');
const path = require('path');

function main() {
  if (process.argv.length < 3) {
    console.error('Usage: node script.js <manifest-file>');
    process.exit(1);
  }

  const manifestPath = path.resolve(process.argv[2]);

  let manifest;
  try {
    const data = fs.readFileSync(manifestPath, 'utf8');
    manifest = JSON.parse(data);
  } catch (err) {
    console.error(`Error reading or parsing manifest file: ${err.message}`);
    process.exit(1);
  }

  if (!Array.isArray(manifest)) {
    console.error('Manifest must be an array of steps');
    process.exit(1);
  }

  for (const step of manifest) {
    if (!step.step || !step.command) {
      console.error('Invalid step in manifest: missing "step" or "command"');
      process.exit(1);
    }

    console.log(`Executing step: ${step.step}`);
    try {
      child_process.execSync(step.command, { stdio: 'inherit' });
    } catch (err) {
      console.error(`Error executing command "${step.command}": ${err.message}`);
      process.exit(1);
    }
  }

  console.log('All steps completed successfully');
}

main();
