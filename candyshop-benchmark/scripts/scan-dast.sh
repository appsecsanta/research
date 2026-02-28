#!/usr/bin/env bash
set -euo pipefail

################################################################################
# scan-dast.sh — Dynamic Application Security Testing
#
# Tools: OWASP ZAP (baseline scan via Docker), Nuclei
# Requires: target containers running (see docker-compose.yml)
#
# Usage: ./scan-dast.sh <RESULTS_DIR>
################################################################################

RESULTS_DIR="${1:?Usage: $0 <RESULTS_DIR>}"
DAST_DIR="${RESULTS_DIR}/dast"
mkdir -p "$DAST_DIR"

# Target URLs — containers must be running on these ports
declare -A URLS=(
  [juice-shop]="http://localhost:3000"
  [broken-crystals]="http://localhost:3001"
  [altoro-mutual]="http://localhost:8080"
  [vulnpy]="http://localhost:5050"
  [dvwa]="http://localhost:8081"
  [webgoat]="http://localhost:8082/WebGoat"
)

TARGETS=(juice-shop broken-crystals altoro-mutual vulnpy dvwa webgoat)

echo "============================================"
echo "  DAST Scanning (ZAP + Nuclei)"
echo "============================================"
echo ""

# ---- ZAP baseline scans ----
echo "--- ZAP baseline scans ---"
for target in "${TARGETS[@]}"; do
  url="${URLS[$target]}"
  outfile="${DAST_DIR}/zap-${target}.json"

  echo "[ZAP] Scanning ${target} (${url})..."
  start_ts=$(date +%s)

  # Run ZAP via Docker with host networking so it can reach localhost ports.
  # -I flag makes ZAP return 0 even if alerts are found (informational scan).
  docker run --rm \
    --network host \
    -v "${DAST_DIR}:/zap/wrk:rw" \
    ghcr.io/zaproxy/zaproxy:stable \
    zap-baseline.py -t "$url" -J "zap-${target}.json" -I || true

  end_ts=$(date +%s)
  elapsed=$((end_ts - start_ts))
  echo "[ZAP] ${target} completed in ${elapsed}s → ${outfile}"
  echo ""
done

# ---- Nuclei scans ----
echo "--- Nuclei scans ---"
for target in "${TARGETS[@]}"; do
  url="${URLS[$target]}"
  outfile="${DAST_DIR}/nuclei-${target}.json"

  echo "[Nuclei] Scanning ${target} (${url})..."
  start_ts=$(date +%s)

  nuclei -u "$url" -json-export "$outfile" -silent -nc || true

  end_ts=$(date +%s)
  elapsed=$((end_ts - start_ts))
  echo "[Nuclei] ${target} completed in ${elapsed}s → ${outfile}"
  echo ""
done

echo "DAST scanning complete. Results in: ${DAST_DIR}"
