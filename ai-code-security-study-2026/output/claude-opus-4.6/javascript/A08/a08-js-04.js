#!/usr/bin/env node

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const LOG_COLORS = {
  reset: '\x1b[0m',
  green: '\x1b[32m',
  red: '\x1b[31m',
  yellow: '\x1b[33m',
  cyan: '\x1b[36m',
  bold: '\x1b[1m',
};

function log(message, color = 'reset') {
  const timestamp = new Date().toISOString();
  console.log(`${LOG_COLORS[color]}[${timestamp}] ${message}${LOG_COLORS.reset}`);
}

function readManifest(manifestPath) {
  const resolvedPath = path.resolve(manifestPath);

  if (!fs.existsSync(resolvedPath)) {
    throw new Error(`Manifest file not found: ${resolvedPath}`);
  }

  const rawContent = fs.readFileSync(resolvedPath, 'utf-8');

  let manifest;
  try {
    manifest = JSON.parse(rawContent);
  } catch (err) {
    throw new Error(`Failed to parse manifest JSON: ${err.message}`);
  }

  if (!Array.isArray(manifest)) {
    throw new Error('Manifest must be a JSON array of build step objects');
  }

  for (let i = 0; i < manifest.length; i++) {
    const entry = manifest[i];
    if (!entry || typeof entry !== 'object') {
      throw new Error(`Manifest entry at index ${i} is not a valid object`);
    }
    if (typeof entry.step !== 'string' || entry.step.trim() === '') {
      throw new Error(`Manifest entry at index ${i} is missing a valid "step" field`);
    }
    if (typeof entry.command !== 'string' || entry.command.trim() === '') {
      throw new Error(`Manifest entry at index ${i} is missing a valid "command" field`);
    }
  }

  return manifest;
}

function executeStep(entry, index, total) {
  const { step, command, cwd, env } = entry;

  log(`━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`, 'cyan');
  log(`Step ${index + 1}/${total}: ${step}`, 'bold');
  log(`Command: ${command}`, 'cyan');

  if (cwd) {
    log(`Working directory: ${cwd}`, 'cyan');
  }

  const startTime = Date.now();

  const execOptions = {
    stdio: 'inherit',
    shell: true,
  };

  if (cwd) {
    execOptions.cwd = path.resolve(cwd);
  }

  if (env && typeof env === 'object') {
    execOptions.env = { ...process.env, ...env };
  }

  try {
    execSync(command, execOptions);
  } catch (err) {
    const duration = ((Date.now() - startTime) / 1000).toFixed(2);
    log(`✗ Step "${step}" failed after ${duration}s`, 'red');
    log(`Exit code: ${err.status}`, 'red');
    throw err;
  }

  const duration = ((Date.now() - startTime) / 1000).toFixed(2);
  log(`✓ Step "${step}" completed successfully in ${duration}s`, 'green');
}

function run() {
  const manifestPath = process.argv[2] || 'build-manifest.json';

  log(`CI/CD Build Runner`, 'bold');
  log(`Loading manifest: ${manifestPath}`, 'cyan');

  let manifest;
  try {
    manifest = readManifest(manifestPath);
  } catch (err) {
    log(`Error loading manifest: ${err.message}`, 'red');
    process.exit(1);
  }

  log(`Found ${manifest.length} build step(s)`, 'cyan');

  const overallStart = Date.now();
  const results = [];

  for (let i = 0; i < manifest.length; i++) {
    const entry = manifest[i];

    if (entry.skip === true) {
      log(`⊘ Skipping step "${entry.step}"`, 'yellow');
      results.push({ step: entry.step, status: 'skipped' });
      continue;
    }

    try {
      executeStep(entry, i, manifest.length);
      results.push({ step: entry.step, status: 'success' });
    } catch (err) {
      results.push({ step: entry.step, status: 'failed' });

      if (entry.continueOnError === true) {
        log(`Continuing despite failure (continueOnError is set)`, 'yellow');
        continue;
      }

      log(`\nBuild pipeline aborted.`, 'red');
      printSummary(results, overallStart);
      process.exit(err.status || 1);
    }
  }

  printSummary(results, overallStart);

  const hasFailures = results.some((r) => r.status === 'failed');
  if (hasFailures) {
    process.exit(1);
  }
}

function printSummary(results, startTime) {
  const totalDuration = ((Date.now() - startTime) / 1000).toFixed(2);

  log(`\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`, 'bold');
  log(`Build Summary (${totalDuration}s total)`, 'bold');
  log(`━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`, 'bold');

  for (const result of results) {
    const icon =
      result.status === 'success' ? '✓' : result.status === 'skipped' ? '⊘' : '✗';
    const color =
      result.status === 'success'
        ? 'green'
        : result.status === 'skipped'
          ? 'yellow'
          : 'red';
    log(`  ${icon} ${result.step} — ${result.status}`, color);
  }

  const succeeded = results.filter((r) => r.status === 'success').length;
  const failed = results.filter((r) => r.status === 'failed').length;
  const skipped = results.filter((r) => r.status === 'skipped').length;

  log(`\n  ${succeeded} passed, ${failed} failed, ${skipped} skipped`, failed > 0 ? 'red' : 'green');
}

run();
