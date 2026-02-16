#!/usr/bin/env node
/**
 * Batch scan websites for security headers.
 *
 * Reads: data/scan_targets.json (list of URLs to scan)
 * Writes: data/headers_scan_raw.json
 *
 * Sends HEAD requests with 10-second timeout, 500ms delay between requests.
 * No authentication needed.
 *
 * Usage: node scripts/scan-headers.js [--limit 100]
 */

const fs = require("fs");
const path = require("path");

const INPUT = path.join(__dirname, "..", "data", "scan_targets.json");
const OUTPUT = path.join(__dirname, "..", "data", "headers_scan_raw.json");

const SECURITY_HEADERS = [
  "content-security-policy",
  "strict-transport-security",
  "x-content-type-options",
  "x-frame-options",
  "permissions-policy",
  "referrer-policy",
  "x-xss-protection",
  "cross-origin-opener-policy",
  "cross-origin-embedder-policy",
  "cross-origin-resource-policy",
];

const TIMEOUT_MS = 10000;
const DELAY_MS = 500;

const delay = (ms) => new Promise((r) => setTimeout(r, ms));

function parseHSTS(value) {
  if (!value) return null;
  const maxAge = value.match(/max-age=(\d+)/i);
  return {
    max_age: maxAge ? parseInt(maxAge[1]) : null,
    includeSubDomains: /includeSubDomains/i.test(value),
    preload: /preload/i.test(value),
  };
}

function parseCSP(value) {
  if (!value) return null;
  const directives = value.split(";").map((d) => d.trim()).filter(Boolean);
  return {
    directive_count: directives.length,
    has_default_src: directives.some((d) => d.startsWith("default-src")),
    has_script_src: directives.some((d) => d.startsWith("script-src")),
    uses_unsafe_inline: /unsafe-inline/i.test(value),
    uses_unsafe_eval: /unsafe-eval/i.test(value),
    uses_nonce: /nonce-/i.test(value),
    uses_strict_dynamic: /strict-dynamic/i.test(value),
    report_only: false,
  };
}

async function scanSite(url) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);

  try {
    const res = await fetch(url, {
      method: "HEAD",
      redirect: "follow",
      signal: controller.signal,
      headers: {
        "User-Agent":
          "AppSecSanta-HeaderStudy/1.0 (+https://appsecsanta.com/security-headers-study-2026)",
      },
    });
    clearTimeout(timer);

    const headers = {};
    for (const h of SECURITY_HEADERS) {
      headers[h] = res.headers.get(h) || null;
    }
    // Also check report-only variant
    headers["content-security-policy-report-only"] =
      res.headers.get("content-security-policy-report-only") || null;
    // Check info leak headers
    headers["x-powered-by"] = res.headers.get("x-powered-by") || null;
    headers["server"] = res.headers.get("server") || null;

    // Parse CSP from either enforcing or report-only header
    const cspValue =
      headers["content-security-policy"] ||
      headers["content-security-policy-report-only"];
    const cspParsed = parseCSP(cspValue);
    if (
      cspParsed &&
      !headers["content-security-policy"] &&
      headers["content-security-policy-report-only"]
    ) {
      cspParsed.report_only = true;
    }

    return {
      url,
      status: res.status,
      redirected: res.redirected,
      final_url: res.url,
      headers,
      hsts_parsed: parseHSTS(headers["strict-transport-security"]),
      csp_parsed: cspParsed,
      scanned_at: new Date().toISOString(),
      error: null,
    };
  } catch (e) {
    clearTimeout(timer);
    return {
      url,
      status: null,
      error: e.name === "AbortError" ? "timeout" : e.message,
      scanned_at: new Date().toISOString(),
    };
  }
}

async function main() {
  const limitArg = process.argv.indexOf("--limit");
  const limit =
    limitArg >= 0 ? parseInt(process.argv[limitArg + 1]) : Infinity;

  if (!fs.existsSync(INPUT)) {
    console.error(`ERROR: ${INPUT} not found.`);
    process.exit(1);
  }

  const targets = JSON.parse(fs.readFileSync(INPUT, "utf-8"));
  const urls = targets.sites.slice(0, limit);

  console.log(`Scanning ${urls.length} sites...`);
  const results = [];
  const startTime = Date.now();

  for (let i = 0; i < urls.length; i++) {
    const url = urls[i].url || `https://${urls[i].domain}`;
    process.stdout.write(
      `\r[${i + 1}/${urls.length}] ${url.substring(0, 60).padEnd(60)}`
    );

    const result = await scanSite(url);
    results.push({
      ...result,
      rank: urls[i].rank,
      domain: urls[i].domain,
    });

    await delay(DELAY_MS);

    // Save progress every 500 sites
    if ((i + 1) % 500 === 0) {
      const elapsed = ((Date.now() - startTime) / 1000 / 60).toFixed(1);
      const progress = {
        metadata: {
          scanned: results.length,
          total: urls.length,
          in_progress: true,
          elapsed_minutes: elapsed,
        },
        results,
      };
      fs.writeFileSync(OUTPUT, JSON.stringify(progress, null, 2) + "\n");
      console.log(`\n  Saved progress: ${results.length} sites (${elapsed} min)`);
    }
  }

  const elapsed = ((Date.now() - startTime) / 1000 / 60).toFixed(1);
  const successful = results.filter((r) => !r.error).length;
  const failed = results.filter((r) => r.error).length;

  const output = {
    metadata: {
      scanned_at: new Date().toISOString(),
      total_scanned: results.length,
      successful,
      failed,
      elapsed_minutes: parseFloat(elapsed),
    },
    results,
  };

  fs.writeFileSync(OUTPUT, JSON.stringify(output, null, 2) + "\n");
  console.log(
    `\nDone in ${elapsed} minutes. ${successful} successful, ${failed} failed.`
  );
}

main().catch(console.error);
