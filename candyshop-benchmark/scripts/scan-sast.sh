#!/usr/bin/env bash
set -euo pipefail

################################################################################
# scan-sast.sh — Static Application Security Testing
#
# Tools: Bearer (all targets), NodeJsScan (JS targets), Bandit (Python targets)
#
# Usage: ./scan-sast.sh <RESULTS_DIR> <SOURCES_DIR>
################################################################################

RESULTS_DIR="${1:?Usage: $0 <RESULTS_DIR> <SOURCES_DIR>}"
SOURCES_DIR="${2:?Usage: $0 <RESULTS_DIR> <SOURCES_DIR>}"
SAST_DIR="${RESULTS_DIR}/sast"
mkdir -p "$SAST_DIR"

TARGETS=(juice-shop broken-crystals altoro-mutual vulnpy dvwa webgoat)
JS_TARGETS=(juice-shop broken-crystals)
PYTHON_TARGETS=(vulnpy)

echo "============================================"
echo "  SAST Scanning (Bearer + NodeJsScan + Bandit)"
echo "============================================"
echo ""

# ---- Bearer scans (all targets) ----
echo "--- Bearer scans ---"
for target in "${TARGETS[@]}"; do
  src="${SOURCES_DIR}/${target}"
  outfile="${SAST_DIR}/bearer-${target}.json"

  if [[ ! -d "$src" ]]; then
    echo "[Bearer] SKIP ${target} — source dir not found: ${src}"
    echo ""
    continue
  fi

  echo "[Bearer] Scanning ${target}..."
  start_ts=$(date +%s)

  bearer scan "$src" \
    --format json \
    --output "$outfile" || true

  end_ts=$(date +%s)
  elapsed=$((end_ts - start_ts))
  echo "[Bearer] ${target} completed in ${elapsed}s → ${outfile}"
  echo ""
done

# ---- NodeJsScan scans (JS targets only) ----
echo "--- NodeJsScan scans ---"
for target in "${JS_TARGETS[@]}"; do
  src="${SOURCES_DIR}/${target}"
  outfile="${SAST_DIR}/njsscan-${target}.json"

  if [[ ! -d "$src" ]]; then
    echo "[NodeJsScan] SKIP ${target} — source dir not found: ${src}"
    echo ""
    continue
  fi

  echo "[NodeJsScan] Scanning ${target}..."
  start_ts=$(date +%s)

  njsscan --json -o "$outfile" "$src" || true

  end_ts=$(date +%s)
  elapsed=$((end_ts - start_ts))
  echo "[NodeJsScan] ${target} completed in ${elapsed}s → ${outfile}"
  echo ""
done

# ---- Bandit scans (Python targets only) ----
echo "--- Bandit scans ---"
for target in "${PYTHON_TARGETS[@]}"; do
  src="${SOURCES_DIR}/${target}"
  outfile="${SAST_DIR}/bandit-${target}.json"

  if [[ ! -d "$src" ]]; then
    echo "[Bandit] SKIP ${target} — source dir not found: ${src}"
    echo ""
    continue
  fi

  echo "[Bandit] Scanning ${target}..."
  start_ts=$(date +%s)

  bandit -r "$src" -f json -o "$outfile" || true

  end_ts=$(date +%s)
  elapsed=$((end_ts - start_ts))
  echo "[Bandit] ${target} completed in ${elapsed}s → ${outfile}"
  echo ""
done

echo "SAST scanning complete. Results in: ${SAST_DIR}"
