#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

function fail(message, code = 1) {
  process.stderr.write(`${message}\n`);
  process.exit(code);
}

function parseArgs(argv) {
  const args = argv.slice(2);
  const opts = {
    manifestPath: null,
    cwd: process.cwd(),
    timeoutMs: 0,
    continueOnError: false,
  };

  for (let i = 0; i < args.length; i++) {
    const a = args[i];

    if (a === '-m' || a === '--manifest') {
      opts.manifestPath = args[++i];
    } else if (a === '--cwd') {
      opts.cwd = args[++i];
    } else if (a === '--timeout') {
      opts.timeoutMs = Number(args[++i] || 0);
    } else if (a === '--continue-on-error') {
      opts.continueOnError = true;
    } else if (!opts.manifestPath && !a.startsWith('-')) {
      opts.manifestPath = a;
    } else if (a === '-h' || a === '--help') {
      printHelpAndExit(0);
    } else {
      fail(`Unknown argument: ${a}\n\n${helpText()}`);
    }
  }

  if (!opts.manifestPath) {
    fail(`Missing manifest path.\n\n${helpText()}`);
  }

  if (!Number.isFinite(opts.timeoutMs) || opts.timeoutMs < 0) {
    fail(`Invalid --timeout value: ${opts.timeoutMs}`);
  }

  return opts;
}

function helpText() {
  const bin = path.basename(process.argv[1] || 'ci-helper.js');
  return (
    `Usage:\n` +
    `  ${bin} --manifest <path>\n` +
    `  ${bin} <path-to-manifest.json>\n\n` +
    `Options:\n` +
    `  -m, --manifest <path>        Path to manifest JSON\n` +
    `  --cwd <path>                 Working directory for commands (default: process.cwd())\n` +
    `  --timeout <ms>               Per-command timeout in milliseconds (0 = no timeout)\n` +
    `  --continue-on-error          Continue executing steps even if one fails\n` +
    `  -h, --help                   Show help\n\n` +
    `Manifest format:\n` +
    `  Either an array of steps:\n` +
    `    [ { "step": "build", "command": "npm run build" }, ... ]\n` +
    `  Or an object with "steps":\n` +
    `    { "steps": [ ... ] }\n`
  );
}

function printHelpAndExit(code) {
  process.stdout.write(helpText());
  process.exit(code);
}

function loadManifest(manifestPath) {
  const abs = path.resolve(manifestPath);
  let raw;
  try {
    raw = fs.readFileSync(abs, 'utf8');
  } catch (err) {
    fail(`Failed to read manifest: ${abs}\n${err.message}`);
  }

  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch (err) {
    fail(`Failed to parse JSON manifest: ${abs}\n${err.message}`);
  }

  const steps = Array.isArray(parsed) ? parsed : parsed && Array.isArray(parsed.steps) ? parsed.steps : null;
  if (!steps) {
    fail(`Invalid manifest structure. Expected an array or an object with "steps" array.`);
  }

  const normalized = steps.map((s, idx) => {
    if (!s || typeof s !== 'object') {
      fail(`Invalid step at index ${idx}: expected object.`);
    }
    const stepName = typeof s.step === 'string' && s.step.trim() ? s.step.trim() : `step-${idx + 1}`;
    const cmd = s.command;
    if (typeof cmd !== 'string' || !cmd.trim()) {
      fail(`Invalid "command" for step "${stepName}" at index ${idx}: expected non-empty string.`);
    }
    const cwd = typeof s.cwd === 'string' && s.cwd.trim() ? s.cwd : null;
    const env = s.env && typeof s.env === 'object' && !Array.isArray(s.env) ? s.env : null;
    const shell = typeof s.shell === 'boolean' ? s.shell : true;

    return {
      step: stepName,
      command: cmd,
      cwd,
      env,
      shell,
    };
  });

  return { absPath: abs, steps: normalized };
}

function runCommand({ command, step, cwd, env, shell }, baseCwd, timeoutMs) {
  return new Promise((resolve) => {
    const start = Date.now();
    const effectiveCwd = cwd ? path.resolve(baseCwd, cwd) : baseCwd;

    process.stdout.write(`\n==> [${step}] ${command}\n`);

    const child = spawn(command, {
      cwd: effectiveCwd,
      env: env ? { ...process.env, ...env } : process.env,
      stdio: 'inherit',
      shell,
      windowsHide: true,
    });

    let timeout = null;
    if (timeoutMs > 0) {
      timeout = setTimeout(() => {
        process.stderr.write(`\n[${step}] Timed out after ${timeoutMs}ms. Sending SIGTERM...\n`);
        try {
          child.kill('SIGTERM');
        } catch (_) {}

        // Force kill if it doesn't exit soon.
        setTimeout(() => {
          try {
            if (!child.killed) child.kill('SIGKILL');
          } catch (_) {}
        }, 5000).unref?.();
      }, timeoutMs);
      timeout.unref?.();
    }

    child.on('error', (err) => {
      if (timeout) clearTimeout(timeout);
      const ms = Date.now() - start;
      resolve({ step, command, code: 1, signal: null, durationMs: ms, error: err });
    });

    child.on('exit', (code, signal) => {
      if (timeout) clearTimeout(timeout);
      const ms = Date.now() - start;
      resolve({ step, command, code: code == null ? 1 : code, signal, durationMs: ms, error: null });
    });
  });
}

async function main() {
  const opts = parseArgs(process.argv);
  const manifest = loadManifest(opts.manifestPath);

  const baseCwd = path.resolve(opts.cwd);

  let overallExitCode = 0;
  const results = [];

  for (const s of manifest.steps) {
    const res = await runCommand(s, baseCwd, opts.timeoutMs);
    results.push(res);

    if (res.error) {
      process.stderr.write(`[${res.step}] Failed to start command: ${res.error.message}\n`);
    }

    if (res.signal) {
      process.stderr.write(`[${res.step}] Exited due to signal: ${res.signal}\n`);
    }

    if (res.code !== 0) {
      process.stderr.write(`[${res.step}] Failed with exit code: ${res.code}\n`);
      overallExitCode = res.code || 1;

      if (!opts.continueOnError) break;
    } else {
      process.stdout.write(`[${res.step}] Completed successfully (${res.durationMs}ms)\n`);
    }
  }

  // If continuing on error, choose first non-zero code as overall (or last non-zero).
  if (opts.continueOnError) {
    const firstFail = results.find((r) => r.code !== 0) || null;
    overallExitCode = firstFail ? (firstFail.code || 1) : 0;
  }

  process.exit(overallExitCode);
}

main().catch((err) => fail(err && err.stack ? err.stack : String(err), 1));
