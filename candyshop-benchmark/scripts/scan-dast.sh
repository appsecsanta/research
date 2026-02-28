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
# Resolve to absolute path (required for Docker volume mounts)
RESULTS_DIR="$(cd "$RESULTS_DIR" 2>/dev/null && pwd || (mkdir -p "$RESULTS_DIR" && cd "$RESULTS_DIR" && pwd))"
DAST_DIR="${RESULTS_DIR}/dast"
mkdir -p "$DAST_DIR"

# Target definitions: name|localhost_url|docker_url
# Nuclei runs natively (uses localhost); ZAP runs in Docker (uses host.docker.internal on macOS)
TARGETS=(
  "juice-shop|http://localhost:3000|http://host.docker.internal:3000"
  "broken-crystals|http://localhost:3001|http://host.docker.internal:3001"
  "altoro-mutual|http://localhost:8080|http://host.docker.internal:8080"
  "vulnpy|http://localhost:5050|http://host.docker.internal:5050"
  "dvwa|http://localhost:8081|http://host.docker.internal:8081"
  "webgoat|http://localhost:8082/WebGoat|http://host.docker.internal:8082/WebGoat"
)

echo "============================================"
echo "  DAST Scanning (ZAP + Nuclei)"
echo "============================================"
echo ""

# ---- ZAP baseline scans ----
echo "--- ZAP baseline scans ---"
for entry in "${TARGETS[@]}"; do
  IFS='|' read -r target local_url docker_url <<< "$entry"
  outfile="${DAST_DIR}/zap-${target}.json"

  echo "[ZAP] Scanning ${target} (${docker_url})..."
  start_ts=$(date +%s)

  # Run ZAP via Docker. On macOS, --network host doesn't work, so we use
  # host.docker.internal to reach host ports from inside the container.
  # -I flag makes ZAP return 0 even if alerts are found (informational scan).
  docker run --rm \
    --add-host=host.docker.internal:host-gateway \
    -v "${DAST_DIR}:/zap/wrk:rw" \
    ghcr.io/zaproxy/zaproxy:stable \
    zap-baseline.py -t "$docker_url" -J "zap-${target}.json" -I || true

  end_ts=$(date +%s)
  elapsed=$((end_ts - start_ts))
  echo "[ZAP] ${target} completed in ${elapsed}s → ${outfile}"
  echo ""
done

# ---- Nuclei scans ----
echo "--- Nuclei scans ---"
for entry in "${TARGETS[@]}"; do
  IFS='|' read -r target local_url docker_url <<< "$entry"
  outfile="${DAST_DIR}/nuclei-${target}.json"

  echo "[Nuclei] Scanning ${target} (${local_url})..."
  start_ts=$(date +%s)

  nuclei -u "$local_url" -json-export "$outfile" -silent -nc || true

  end_ts=$(date +%s)
  elapsed=$((end_ts - start_ts))
  echo "[Nuclei] ${target} completed in ${elapsed}s → ${outfile}"
  echo ""
done

echo "DAST scanning complete. Results in: ${DAST_DIR}"
