#!/usr/bin/env bash
set -euo pipefail

################################################################################
# scan-sca.sh — Software Composition Analysis
#
# Tools: npm audit (JS targets), pip-audit (Python targets),
#        OWASP Dependency-Check (all targets)
#
# Usage: ./scan-sca.sh <RESULTS_DIR> <SOURCES_DIR>
################################################################################

RESULTS_DIR="${1:?Usage: $0 <RESULTS_DIR> <SOURCES_DIR>}"
SOURCES_DIR="${2:?Usage: $0 <RESULTS_DIR> <SOURCES_DIR>}"
SCA_DIR="${RESULTS_DIR}/sca"
mkdir -p "$SCA_DIR"

NPM_TARGETS=(juice-shop broken-crystals)
PIP_TARGETS=(vulnpy)
TARGETS=(juice-shop broken-crystals altoro-mutual vulnpy dvwa webgoat)

echo "============================================"
echo "  SCA Scanning (npm audit + pip-audit + Dep-Check)"
echo "============================================"
echo ""

# ---- npm audit (JS targets) ----
echo "--- npm audit scans ---"
for target in "${NPM_TARGETS[@]}"; do
  src="${SOURCES_DIR}/${target}"
  outfile="${SCA_DIR}/npm-audit-${target}.json"

  if [[ ! -d "$src" ]]; then
    echo "[npm audit] SKIP ${target} — source dir not found: ${src}"
    echo ""
    continue
  fi

  if [[ ! -f "${src}/package.json" ]]; then
    echo "[npm audit] SKIP ${target} — no package.json found"
    echo ""
    continue
  fi

  echo "[npm audit] Scanning ${target}..."
  start_ts=$(date +%s)

  # npm audit returns non-zero when vulnerabilities are found, so || true
  (cd "$src" && npm audit --json > "$outfile" 2>&1) || true

  end_ts=$(date +%s)
  elapsed=$((end_ts - start_ts))
  echo "[npm audit] ${target} completed in ${elapsed}s → ${outfile}"
  echo ""
done

# ---- pip-audit (Python targets) ----
echo "--- pip-audit scans ---"
for target in "${PIP_TARGETS[@]}"; do
  src="${SOURCES_DIR}/${target}"
  outfile="${SCA_DIR}/pip-audit-${target}.json"

  if [[ ! -d "$src" ]]; then
    echo "[pip-audit] SKIP ${target} — source dir not found: ${src}"
    echo ""
    continue
  fi

  reqfile="${src}/requirements.txt"
  if [[ ! -f "$reqfile" ]]; then
    echo "[pip-audit] SKIP ${target} — no requirements.txt found"
    echo ""
    continue
  fi

  echo "[pip-audit] Scanning ${target}..."
  start_ts=$(date +%s)

  pip-audit -r "$reqfile" --format json --output "$outfile" || true

  end_ts=$(date +%s)
  elapsed=$((end_ts - start_ts))
  echo "[pip-audit] ${target} completed in ${elapsed}s → ${outfile}"
  echo ""
done

# ---- OWASP Dependency-Check (all targets) ----
echo "--- OWASP Dependency-Check scans ---"
for target in "${TARGETS[@]}"; do
  src="${SOURCES_DIR}/${target}"
  outdir="${SCA_DIR}/depcheck-${target}"
  mkdir -p "$outdir"

  if [[ ! -d "$src" ]]; then
    echo "[Dep-Check] SKIP ${target} — source dir not found: ${src}"
    echo ""
    continue
  fi

  echo "[Dep-Check] Scanning ${target}..."
  start_ts=$(date +%s)

  dependency-check.sh \
    --project "$target" \
    --scan "$src" \
    --format JSON \
    --out "$outdir" \
    --enableExperimental || true

  end_ts=$(date +%s)
  elapsed=$((end_ts - start_ts))
  echo "[Dep-Check] ${target} completed in ${elapsed}s → ${outdir}"
  echo ""
done

echo "SCA scanning complete. Results in: ${SCA_DIR}"
