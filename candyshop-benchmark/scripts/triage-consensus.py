#!/usr/bin/env python3
"""
triage-consensus.py — Multi-tool consensus triage for CandyShop Benchmark

Groups normalized scan findings by (target, CWE, location) similarity,
then applies consensus rules to auto-classify true positives vs. pending.

Usage:
    python3 triage-consensus.py <normalized-csv> <ground-truth-dir> <triage-output-dir>

Example:
    python3 scripts/triage-consensus.py results/normalized-all.csv ground-truth/ triage/
"""

import csv
import os
import sys
from collections import defaultdict
from urllib.parse import urlparse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SEVERITY_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}


def severity_rank(sev):
    """Return numeric rank for a severity string (higher = worse)."""
    return SEVERITY_ORDER.get((sev or "").strip().lower(), -1)


def highest_severity(severities):
    """Pick the highest severity label from a list."""
    best = max(severities, key=severity_rank, default="unknown")
    return best if severity_rank(best) >= 0 else "unknown"


def extract_basename(location):
    """
    Extract the file basename from a location string.

    Handles:
      - File paths: /src/routes/search.ts → search.ts
      - URLs: http://localhost:3000/rest/products/search → /rest/products/search
      - Line-number suffixes: /src/app.js:42 → app.js
    """
    if not location:
        return ""

    loc = location.strip()

    # If it looks like a URL, extract the path portion
    if loc.startswith("http://") or loc.startswith("https://"):
        parsed = urlparse(loc)
        loc = parsed.path

    # Strip line/column numbers (e.g. :42 or :42:10)
    parts = loc.split(":")
    if len(parts) > 1 and parts[-1].isdigit():
        loc = parts[0]
        if len(parts) > 2 and parts[-2].isdigit():
            loc = ":".join(parts[:-2])

    return os.path.basename(loc) if loc else ""


def extract_url_path(location):
    """
    If location is a URL, return its path component for comparison.
    Returns empty string for non-URL locations.
    """
    if not location:
        return ""
    loc = location.strip()
    if loc.startswith("http://") or loc.startswith("https://"):
        return urlparse(loc).path
    return ""


def locations_match(loc_a, loc_b):
    """
    Fuzzy location matching.

    Two locations match if:
      - Both have the same file basename (non-empty), OR
      - Both are URLs and share the same path component
    """
    if not loc_a or not loc_b:
        return False

    # URL path matching
    url_a = extract_url_path(loc_a)
    url_b = extract_url_path(loc_b)
    if url_a and url_b:
        return url_a == url_b

    # Basename matching
    base_a = extract_basename(loc_a)
    base_b = extract_basename(loc_b)
    if base_a and base_b:
        return base_a == base_b

    return False


def normalize_cwe(cwe_str):
    """Normalize CWE identifiers: 'CWE-79', 'cwe-79', '79' → 'CWE-79'."""
    if not cwe_str:
        return ""
    cwe = cwe_str.strip().upper()
    if cwe.startswith("CWE-"):
        return cwe
    # Bare number
    if cwe.isdigit():
        return f"CWE-{cwe}"
    return cwe


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_normalized(csv_path):
    """
    Load normalized findings from CSV.

    Expected columns:
        finding_id, tool, target, category, cwe, severity, location,
        description, raw_id
    """
    findings = []
    if not os.path.isfile(csv_path):
        print(f"WARNING: normalized CSV not found: {csv_path}", file=sys.stderr)
        return findings

    with open(csv_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            row["cwe"] = normalize_cwe(row.get("cwe", ""))
            row["severity"] = (row.get("severity") or "unknown").strip().lower()
            row["target"] = (row.get("target") or "").strip()
            row["location"] = (row.get("location") or "").strip()
            row["tool"] = (row.get("tool") or "").strip()
            row["description"] = (row.get("description") or "").strip()
            findings.append(row)
    return findings


def load_ground_truth(gt_dir):
    """
    Load all ground-truth CSV files from a directory.

    Expected columns per file:
        vuln_id, cwe, category, description, location, difficulty, source

    The target name is derived from the filename:
        juice-shop.csv → juice-shop
    """
    gt_entries = []
    if not os.path.isdir(gt_dir):
        print(f"WARNING: ground-truth dir not found: {gt_dir}", file=sys.stderr)
        return gt_entries

    for fname in sorted(os.listdir(gt_dir)):
        if not fname.endswith(".csv"):
            continue
        target = fname.rsplit(".", 1)[0]  # juice-shop.csv → juice-shop
        fpath = os.path.join(gt_dir, fname)
        try:
            with open(fpath, newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    row["target"] = target
                    row["cwe"] = normalize_cwe(row.get("cwe", ""))
                    row["location"] = (row.get("location") or "").strip()
                    gt_entries.append(row)
        except Exception as exc:
            print(
                f"WARNING: could not read {fpath}: {exc}",
                file=sys.stderr,
            )
    return gt_entries


# ---------------------------------------------------------------------------
# Grouping
# ---------------------------------------------------------------------------

def group_findings(findings):
    """
    Group findings by (target, CWE) then merge by location similarity.

    Returns a dict:
        group_key → list of finding dicts
    where group_key = (target, cwe, representative_location)

    Within each (target, cwe) bucket, findings are further split into
    sub-groups by fuzzy location matching. Two findings end up in the same
    sub-group if either can be linked (transitively) via location similarity.
    """
    # First pass: bucket by (target, cwe)
    buckets = defaultdict(list)
    for f in findings:
        key = (f["target"], f["cwe"])
        buckets[key].append(f)

    # Second pass: within each bucket, cluster by location similarity
    groups = {}  # (target, cwe, cluster_idx) → [findings]
    for (target, cwe), bucket_findings in buckets.items():
        clusters = []  # list of lists
        for f in bucket_findings:
            merged = False
            for cluster in clusters:
                for existing in cluster:
                    if locations_match(f["location"], existing["location"]):
                        cluster.append(f)
                        merged = True
                        break
                if merged:
                    break
            if not merged:
                clusters.append([f])

        for idx, cluster in enumerate(clusters):
            groups[(target, cwe, idx)] = cluster

    return groups


# ---------------------------------------------------------------------------
# Ground-truth matching
# ---------------------------------------------------------------------------

def build_gt_index(gt_entries):
    """
    Build a lookup: (target, cwe) → list of ground-truth rows
    for fast matching.
    """
    index = defaultdict(list)
    for entry in gt_entries:
        key = (entry["target"], entry["cwe"])
        index[key].append(entry)
    return index


def check_ground_truth(target, cwe, gt_index):
    """
    Return True if any ground-truth entry matches this (target, cwe).
    """
    return len(gt_index.get((target, cwe), [])) > 0


# ---------------------------------------------------------------------------
# Consensus triage
# ---------------------------------------------------------------------------

def triage_groups(groups, gt_index):
    """
    Apply consensus rules to each finding group.

    Returns a list of triage result dicts (one per group), sorted by target
    then group ID.
    """
    results = []

    # Counters per target for generating sequential IDs
    target_counters = defaultdict(int)

    # Sort groups for deterministic output
    sorted_keys = sorted(groups.keys(), key=lambda k: (k[0], k[1], k[2]))

    for (target, cwe, _cluster_idx) in sorted_keys:
        cluster = groups[(target, cwe, _cluster_idx)]
        tools = sorted(set(f["tool"] for f in cluster))
        tool_count = len(tools)

        # Pick highest severity
        severities = [f["severity"] for f in cluster]
        sev = highest_severity(severities)

        # Pick a representative location (first non-empty)
        location = ""
        for f in cluster:
            if f["location"]:
                location = f["location"]
                break

        # Pick a representative description (first non-empty)
        description = ""
        for f in cluster:
            if f["description"]:
                description = f["description"]
                break

        # Ground-truth match?
        gt_match = check_ground_truth(target, cwe, gt_index)

        # Consensus rules
        if tool_count >= 2:
            verdict = "TP"
            confidence = "high"
        elif tool_count == 1 and gt_match:
            verdict = "TP"
            confidence = "medium"
        else:
            verdict = "pending"
            confidence = "low"

        # Generate group ID
        target_counters[target] += 1
        seq = target_counters[target]
        group_id = f"GRP-{target}-{cwe}-{seq:03d}"

        results.append({
            "finding_group_id": group_id,
            "tools": "|".join(tools),
            "target": target,
            "cwe": cwe,
            "severity": sev,
            "location": location,
            "description": description,
            "verdict": verdict,
            "confidence": confidence,
            "ground_truth_match": "yes" if gt_match else "no",
            "tool_count": str(tool_count),
        })

    return results


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

TRIAGE_COLUMNS = [
    "finding_group_id",
    "tools",
    "target",
    "cwe",
    "severity",
    "location",
    "description",
    "verdict",
    "confidence",
    "ground_truth_match",
    "tool_count",
]


def write_triage_files(results, output_dir):
    """
    Write per-target triage CSVs: <output_dir>/<target>-auto.csv

    Returns a dict of per-target stats: {target: {"tp": N, "pending": M}}
    """
    os.makedirs(output_dir, exist_ok=True)

    # Group results by target
    by_target = defaultdict(list)
    for r in results:
        by_target[r["target"]].append(r)

    stats = {}
    for target in sorted(by_target.keys()):
        rows = by_target[target]
        outpath = os.path.join(output_dir, f"{target}-auto.csv")

        with open(outpath, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=TRIAGE_COLUMNS)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

        tp_count = sum(1 for r in rows if r["verdict"] == "TP")
        pending_count = sum(1 for r in rows if r["verdict"] == "pending")
        stats[target] = {"tp": tp_count, "pending": pending_count}

    return stats


def print_summary(stats):
    """Print per-target and total summary to stderr."""
    total_tp = 0
    total_pending = 0

    for target in sorted(stats.keys()):
        s = stats[target]
        total_tp += s["tp"]
        total_pending += s["pending"]
        print(
            f"{target}: {s['tp']} TP (auto), {s['pending']} pending",
            file=sys.stderr,
        )

    print(
        f"Total: {total_tp} TP, {total_pending} pending",
        file=sys.stderr,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) != 4:
        print(
            "Usage: python3 triage-consensus.py "
            "<normalized-csv> <ground-truth-dir> <triage-output-dir>",
            file=sys.stderr,
        )
        sys.exit(1)

    normalized_csv = sys.argv[1]
    gt_dir = sys.argv[2]
    output_dir = sys.argv[3]

    # Load data
    findings = load_normalized(normalized_csv)
    gt_entries = load_ground_truth(gt_dir)

    if not findings:
        print("No findings loaded. Nothing to triage.", file=sys.stderr)
        sys.exit(0)

    print(
        f"Loaded {len(findings)} findings, "
        f"{len(gt_entries)} ground-truth entries",
        file=sys.stderr,
    )

    # Build ground-truth index
    gt_index = build_gt_index(gt_entries)

    # Group and triage
    groups = group_findings(findings)
    results = triage_groups(groups, gt_index)

    # Write output
    stats = write_triage_files(results, output_dir)

    # Summary
    print("", file=sys.stderr)
    print_summary(stats)


if __name__ == "__main__":
    main()
