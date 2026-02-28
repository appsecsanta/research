#!/usr/bin/env bash
set -euo pipefail

################################################################################
# run-all.sh — CandyShop Benchmark orchestrator
#
# Master script that runs all scan phases in order:
#   1. Record metadata (date, hostname, OS, tool versions)
#   2. Build & start containers via docker compose
#   3. Container image scanning (Trivy + Grype)
#   4. SAST scanning (Bearer + NodeJsScan + Bandit)
#   5. SCA scanning (npm audit + pip-audit + Dependency-Check)
#   6. IaC scanning (Checkov)
#   7. DAST scanning (ZAP + Nuclei) — last because containers must be running
#   8. Tear down containers
#   9. Print summary
#
# Usage: ./run-all.sh [RESULTS_DIR]
#   Defaults to results/YYYY-MM-DD if not provided.
################################################################################

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BENCHMARK_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
DATE_TAG="$(date +%Y-%m-%d)"
RESULTS_DIR="${1:-${BENCHMARK_DIR}/results/${DATE_TAG}}"
SOURCES_DIR="${BENCHMARK_DIR}/sources"

mkdir -p "$RESULTS_DIR"

echo "╔══════════════════════════════════════════════╗"
echo "║     CandyShop Benchmark — Full Scan Run      ║"
echo "╠══════════════════════════════════════════════╣"
echo "║  Date:    ${DATE_TAG}                            ║"
echo "║  Results: ${RESULTS_DIR}"
echo "╚══════════════════════════════════════════════╝"
echo ""

TOTAL_START=$(date +%s)

# ---- Step 1: Record metadata ----
echo "=== Step 1/8: Recording metadata ==="
META_FILE="${RESULTS_DIR}/metadata.txt"
{
  echo "CandyShop Benchmark — Scan Metadata"
  echo "===================================="
  echo "Date:     $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  echo "Hostname: $(hostname)"
  echo "OS:       $(uname -srm)"
  echo ""

  if command -v sw_vers &>/dev/null; then
    echo "macOS:    $(sw_vers -productVersion) ($(sw_vers -buildVersion))"
  fi

  echo ""
  echo "--- Docker ---"
  docker --version 2>/dev/null || echo "docker: not found"
  docker compose version 2>/dev/null || echo "docker compose: not found"

  echo ""
  echo "--- Container Scanners ---"
  trivy --version 2>/dev/null || echo "trivy: not found"
  grype version 2>/dev/null || echo "grype: not found"

  echo ""
  echo "--- SAST Tools ---"
  bearer version 2>/dev/null || echo "bearer: not found"
  njsscan --version 2>/dev/null || echo "njsscan: not found"
  bandit --version 2>/dev/null || echo "bandit: not found"

  echo ""
  echo "--- SCA Tools ---"
  npm --version 2>/dev/null && echo "(npm audit available)" || echo "npm: not found"
  pip-audit --version 2>/dev/null || echo "pip-audit: not found"
  dependency-check --version 2>/dev/null || echo "dependency-check: not found"

  echo ""
  echo "--- DAST Tools ---"
  echo "ZAP: via Docker (ghcr.io/zaproxy/zaproxy:stable)"
  nuclei --version 2>/dev/null || echo "nuclei: not found"

  echo ""
  echo "--- IaC Tools ---"
  checkov --version 2>/dev/null || echo "checkov: not found"
} > "$META_FILE" 2>&1

echo "Metadata saved to: ${META_FILE}"
echo ""

# ---- Step 2: Build and start containers ----
echo "=== Step 2/8: Starting containers ==="
cd "$BENCHMARK_DIR"
docker compose build || true
docker compose up -d

echo "Waiting 60s for containers to pass health checks..."
sleep 60

echo "Container status:"
docker compose ps
echo ""

# ---- Step 3: Container image scanning ----
echo "=== Step 3/8: Container image scanning ==="
step_start=$(date +%s)
bash "${SCRIPT_DIR}/scan-container.sh" "$RESULTS_DIR"
step_end=$(date +%s)
echo "Container scanning took $((step_end - step_start))s"
echo ""

# ---- Step 4: SAST scanning ----
echo "=== Step 4/8: SAST scanning ==="
step_start=$(date +%s)
bash "${SCRIPT_DIR}/scan-sast.sh" "$RESULTS_DIR" "$SOURCES_DIR"
step_end=$(date +%s)
echo "SAST scanning took $((step_end - step_start))s"
echo ""

# ---- Step 5: SCA scanning ----
echo "=== Step 5/8: SCA scanning ==="
step_start=$(date +%s)
bash "${SCRIPT_DIR}/scan-sca.sh" "$RESULTS_DIR" "$SOURCES_DIR"
step_end=$(date +%s)
echo "SCA scanning took $((step_end - step_start))s"
echo ""

# ---- Step 6: IaC scanning ----
echo "=== Step 6/8: IaC scanning ==="
step_start=$(date +%s)
bash "${SCRIPT_DIR}/scan-iac.sh" "$RESULTS_DIR" "$BENCHMARK_DIR"
step_end=$(date +%s)
echo "IaC scanning took $((step_end - step_start))s"
echo ""

# ---- Step 7: DAST scanning ----
echo "=== Step 7/8: DAST scanning ==="
echo "(DAST runs last — containers must be up for dynamic testing)"
step_start=$(date +%s)
bash "${SCRIPT_DIR}/scan-dast.sh" "$RESULTS_DIR"
step_end=$(date +%s)
echo "DAST scanning took $((step_end - step_start))s"
echo ""

# ---- Step 8: Tear down containers ----
echo "=== Step 8/8: Tearing down containers ==="
cd "$BENCHMARK_DIR"
docker compose down -v
echo ""

# ---- Summary ----
TOTAL_END=$(date +%s)
TOTAL_ELAPSED=$((TOTAL_END - TOTAL_START))
TOTAL_MIN=$((TOTAL_ELAPSED / 60))
TOTAL_SEC=$((TOTAL_ELAPSED % 60))

echo "╔══════════════════════════════════════════════╗"
echo "║           Scan Run Complete                   ║"
echo "╠══════════════════════════════════════════════╣"
echo "║  Total time: ${TOTAL_MIN}m ${TOTAL_SEC}s"
echo "║  Results:    ${RESULTS_DIR}"
echo "╚══════════════════════════════════════════════╝"
echo ""

echo "Result files:"
find "$RESULTS_DIR" -type f -name "*.json" -o -name "*.txt" | sort | while read -r f; do
  size=$(wc -c < "$f" | tr -d ' ')
  echo "  ${f} (${size} bytes)"
done
