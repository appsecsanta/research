#!/usr/bin/env node
/**
 * Collect download stats from npm, PyPI, and Docker Hub.
 *
 * Reads: data/oss_tools_github_raw.json
 * Writes: data/oss_tools_downloads.json
 *
 * No authentication needed. Rate-limited with delays.
 * Usage: node scripts/collect-downloads.js
 */

const fs = require("fs");
const path = require("path");

const INPUT = path.join(__dirname, "..", "data", "oss_tools_github_raw.json");
const OUTPUT = path.join(__dirname, "..", "data", "oss_tools_downloads.json");

const delay = (ms) => new Promise((r) => setTimeout(r, ms));

// Known package names per tool (can't always auto-detect from GitHub)
// Map: tool slug -> { npm?: string, pypi?: string, docker?: string }
const PACKAGE_MAP = {
  semgrep: { pypi: "semgrep", docker: "semgrep/semgrep" },
  trivy: { docker: "aquasec/trivy" },
  nuclei: { docker: "projectdiscovery/nuclei" },
  grype: { docker: "anchore/grype" },
  syft: { docker: "anchore/syft" },
  bandit: { pypi: "bandit" },
  gosec: { docker: "securego/gosec" },
  brakeman: {}, // Ruby gem — skip
  checkov: { pypi: "checkov", docker: "bridgecrew/checkov" },
  tfsec: { docker: "aquasec/tfsec" },
  kics: { docker: "checkmarx/kics" },
  terrascan: { docker: "tenable/terrascan" },
  kubescape: { docker: "kubescape/kubescape" },
  falco: { docker: "falcosecurity/falco" },
  trufflehog: { pypi: "truffleHog", docker: "trufflesecurity/trufflehog" },
  gitleaks: { docker: "zricethezav/gitleaks" },
  bearer: { docker: "bearer/bearer" },
  "osv-scanner": {},
  zap: { docker: "zaproxy/zap-stable" },
  defectdojo: { docker: "defectdojo/defectdojo-django" },
  mobsf: { pypi: "mobsf", docker: "opensecurity/mobile-security-framework-mobsf" },
  spotbugs: {}, // Java/Maven only
  pmd: {}, // Java/Maven only
  promptfoo: { npm: "promptfoo" },
  "detect-secrets": { pypi: "detect-secrets" },
  wapiti: { pypi: "wapiti3" },
  nikto: {}, // Perl, no package manager
  nodejsscan: { pypi: "nodejsscan" },
  renovate: { npm: "renovate", docker: "renovate/renovate" },
  conftest: { docker: "openpolicyagent/conftest" },
  "owasp-dependency-check": { docker: "owasp/dependency-check" },
  frida: { pypi: "frida", npm: "frida" },
  "llm-guard": { pypi: "llm-guard" },
  garak: { pypi: "garak" },
  deepteam: { pypi: "deepteam" },
  mitmproxy: { pypi: "mitmproxy" },
  sonarqube: { docker: "sonarqube" },
  "dependency-track": { docker: "dependencytrack/apiserver" },
  faraday: { pypi: "faradaysec" },
  kyverno: { docker: "ghcr.io/kyverno/kyverno" },
  "kube-bench": { docker: "aquasec/kube-bench" },
  kubearmor: { docker: "kubearmor/kubearmor" },
  "opa-gatekeeper": { docker: "openpolicyagent/gatekeeper" },
  modsecurity: { docker: "owasp/modsecurity" },
  pyrit: { pypi: "pyrit-ai" },
  "nemo-guardrails": { pypi: "nemoguardrails" },
};

async function fetchJSON(url) {
  try {
    const res = await fetch(url, {
      headers: { "User-Agent": "AppSecSanta-Study/1.0" },
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

async function getNpmDownloads(pkg) {
  // Last 30 days downloads
  const data = await fetchJSON(
    `https://api.npmjs.org/downloads/point/last-month/${pkg}`
  );
  return data?.downloads || null;
}

async function getPypiDownloads(pkg) {
  // pypistats.org API — last month
  const data = await fetchJSON(
    `https://pypistats.org/api/packages/${pkg}/recent`
  );
  return data?.data?.last_month || null;
}

async function getDockerPulls(image) {
  // Docker Hub API — total pulls
  // Only works for docker.io images, not ghcr.io
  if (image.startsWith("ghcr.io/")) return null;
  const data = await fetchJSON(
    `https://hub.docker.com/v2/repositories/${image}/`
  );
  return data?.pull_count || null;
}

async function main() {
  const raw = JSON.parse(fs.readFileSync(INPUT, "utf-8"));
  const results = [];

  console.log(`Collecting download data for ${raw.tools.length} tools...`);

  for (const tool of raw.tools) {
    const pkgs = PACKAGE_MAP[tool.slug] || {};
    const downloads = {};

    if (pkgs.npm) {
      downloads.npm_monthly = await getNpmDownloads(pkgs.npm);
      await delay(200);
    }
    if (pkgs.pypi) {
      downloads.pypi_monthly = await getPypiDownloads(pkgs.pypi);
      await delay(200);
    }
    if (pkgs.docker) {
      downloads.docker_pulls = await getDockerPulls(pkgs.docker);
      await delay(200);
    }

    const hasAny = Object.values(downloads).some((v) => v !== null && v !== undefined);

    results.push({
      slug: tool.slug,
      name: tool.name,
      downloads: hasAny ? downloads : null,
    });

    if (hasAny) {
      console.log(`${tool.name}: ${JSON.stringify(downloads)}`);
    }
  }

  const output = {
    metadata: {
      collected_at: new Date().toISOString(),
      tool_count: results.length,
      tools_with_downloads: results.filter((r) => r.downloads).length,
    },
    tools: results,
  };

  fs.writeFileSync(OUTPUT, JSON.stringify(output, null, 2) + "\n");
  console.log(`\nDone. ${output.metadata.tools_with_downloads} tools with download data.`);
}

main().catch(console.error);
