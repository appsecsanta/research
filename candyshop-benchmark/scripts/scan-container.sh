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

# Target images — keys are target names, values are Docker image references
declare -A IMAGES=(
  [juice-shop]="bkimminich/juice-shop:latest"
  [broken-crystals]="neuralegion/brokencrystals:latest"
  [altoro-mutual]="candyshop-benchmark-altoro-mutual:latest"
  [vulnpy]="candyshop-benchmark-vulnpy:latest"
  [dvwa]="vulnerables/web-dvwa:latest"
  [webgoat]="webgoat/webgoat:latest"
)

TARGETS=(juice-shop broken-crystals altoro-mutual vulnpy dvwa webgoat)

echo "============================================"
echo "  Container Image Scanning (Trivy + Grype)"
echo "============================================"
echo ""

# ---- Trivy scans ----
echo "--- Trivy scans ---"
for target in "${TARGETS[@]}"; do
  image="${IMAGES[$target]}"
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
for target in "${TARGETS[@]}"; do
  image="${IMAGES[$target]}"
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
