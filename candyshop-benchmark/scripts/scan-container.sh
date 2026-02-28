#!/usr/bin/env bash
set -euo pipefail

################################################################################
# scan-container.sh — Container image scanning with Trivy and Grype
#
# Scans Docker images for all 6 CandyShop Benchmark targets.
# Pre-built images are pulled from registries; locally-built images must exist.
#
# Usage: ./scan-container.sh <RESULTS_DIR>
################################################################################

RESULTS_DIR="${1:?Usage: $0 <RESULTS_DIR>}"
CONTAINER_DIR="${RESULTS_DIR}/container"
mkdir -p "$CONTAINER_DIR"

# Target images — parallel arrays (bash 3.2 compatible)
TARGETS=(juice-shop broken-crystals altoro-mutual vulnpy dvwa webgoat)
IMAGES=(
  "bkimminich/juice-shop:latest"
  "neuralegion/brokencrystals:latest"
  "candyshop-benchmark-altoro-mutual:latest"
  "candyshop-benchmark-vulnpy:latest"
  "vulnerables/web-dvwa:latest"
  "webgoat/webgoat:latest"
)

echo "============================================"
echo "  Container Image Scanning (Trivy + Grype)"
echo "============================================"
echo ""

# ---- Trivy scans ----
echo "--- Trivy scans ---"
for i in $(seq 0 $((${#TARGETS[@]} - 1))); do
  target="${TARGETS[$i]}"
  image="${IMAGES[$i]}"
  outfile="${CONTAINER_DIR}/trivy-${target}.json"

  echo "[Trivy] Scanning ${target} (${image})..."
  start_ts=$(date +%s)

  trivy image \
    --format json \
    --output "$outfile" \
    "$image" || true

  end_ts=$(date +%s)
  elapsed=$((end_ts - start_ts))
  echo "[Trivy] ${target} completed in ${elapsed}s → ${outfile}"
  echo ""
done

# ---- Grype scans ----
echo "--- Grype scans ---"
for i in $(seq 0 $((${#TARGETS[@]} - 1))); do
  target="${TARGETS[$i]}"
  image="${IMAGES[$i]}"
  outfile="${CONTAINER_DIR}/grype-${target}.json"

  echo "[Grype] Scanning ${target} (${image})..."
  start_ts=$(date +%s)

  grype "$image" -o json > "$outfile" || true

  end_ts=$(date +%s)
  elapsed=$((end_ts - start_ts))
  echo "[Grype] ${target} completed in ${elapsed}s → ${outfile}"
  echo ""
done

echo "Container scanning complete. Results in: ${CONTAINER_DIR}"
