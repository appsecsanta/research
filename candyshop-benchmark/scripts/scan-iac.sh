#!/usr/bin/env bash
set -euo pipefail

################################################################################
# scan-iac.sh — Infrastructure-as-Code scanning with Checkov
#
# Scans the entire benchmark directory for Dockerfile and docker-compose issues.
#
# Usage: ./scan-iac.sh <RESULTS_DIR> [BENCHMARK_DIR]
################################################################################

RESULTS_DIR="${1:?Usage: $0 <RESULTS_DIR> [BENCHMARK_DIR]}"
BENCHMARK_DIR="${2:-$(cd "$(dirname "$0")/.." && pwd)}"
IAC_DIR="${RESULTS_DIR}/iac"
mkdir -p "$IAC_DIR"

OUTFILE="${IAC_DIR}/checkov.json"

echo "============================================"
echo "  IaC Scanning (Checkov)"
echo "============================================"
echo ""
echo "Benchmark directory: ${BENCHMARK_DIR}"
echo ""

echo "[Checkov] Scanning Dockerfiles and docker-compose files..."
start_ts=$(date +%s)

checkov \
  -d "$BENCHMARK_DIR" \
  --framework dockerfile docker_compose \
  --output json \
  > "$OUTFILE" || true

end_ts=$(date +%s)
elapsed=$((end_ts - start_ts))
echo "[Checkov] Completed in ${elapsed}s → ${OUTFILE}"
echo ""

echo "IaC scanning complete. Results in: ${IAC_DIR}"
