#!/usr/bin/env python3
"""
Validation Template Generator
AI-Generated Code Security Study 2026

Reads all scan results from scans/, deduplicates findings (same file + same CWE
from different tools = one row), and generates a validation CSV for manual review.

Usage:
    python3 analysis/validate.py                # Generate validation.csv
    python3 analysis/validate.py --output out.csv   # Custom output path
    python3 analysis/validate.py --model gpt-5.2    # Only one model
"""

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
STUDY_DIR = SCRIPT_DIR.parent
SCANS_DIR = STUDY_DIR / "scans"
DEFAULT_OUTPUT = SCRIPT_DIR / "validation.csv"

# Severity ranking for "take highest" logic
SEVERITY_RANK = {
    "CRITICAL": 5,
    "HIGH": 4,
    "MEDIUM": 3,
    "LOW": 2,
    "INFO": 1,
}

CSV_COLUMNS = [
    "finding_id",
    "model",
    "file",
    "line",
    "cwe",
    "owasp",
    "severity",
    "tools",
    "validated",
    "notes",
]


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def load_scan_results(scans_dir, model_filter=None):
    """
    Load all scan JSON files from scans/{model_id}/{tool}.json.

    Returns a flat list of finding dicts, each with an added 'tool' field.
    """
    all_findings = []

    if not scans_dir.is_dir():
        return all_findings

    for model_dir in sorted(scans_dir.iterdir()):
        if not model_dir.is_dir() or model_dir.name.startswith("."):
            continue

        model_id = model_dir.name

        if model_filter and model_id != model_filter:
            continue

        for scan_file in sorted(model_dir.glob("*.json")):
            try:
                with open(scan_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                print(f"  WARNING: Could not read {scan_file}: {e}", file=sys.stderr)
                continue

            tool_name = data.get("tool", scan_file.stem)
            scan_model = data.get("model", model_id)

            for finding in data.get("findings", []):
                finding_copy = dict(finding)
                finding_copy["_tool"] = tool_name
                finding_copy["_model"] = scan_model
                all_findings.append(finding_copy)

    return all_findings


def highest_severity(*severities):
    """Return the highest severity from a list of severity strings."""
    best = "LOW"
    best_rank = 0
    for sev in severities:
        rank = SEVERITY_RANK.get(sev.upper(), 0) if sev else 0
        if rank > best_rank:
            best_rank = rank
            best = sev.upper()
    return best


def deduplicate_findings(raw_findings):
    """
    Deduplicate findings: same model + same file + same CWE from different
    tools collapses into one row with a combined tool list.

    The dedup key is (model, file, cwe). We keep the lowest line number,
    the highest severity, and merge the OWASP field (take first non-empty).

    Returns a list of deduped finding dicts.
    """
    # Group by (model, file, cwe)
    groups = defaultdict(list)
    for f in raw_findings:
        cwe = f.get("cwe", "").strip()
        if not cwe:
            # Findings without a CWE are not deduped against each other;
            # use tool+rule_id as additional key component so they stay separate
            key = (f["_model"], f.get("file", ""), f"_nocwe_{f['_tool']}_{f.get('rule_id', '')}")
        else:
            key = (f["_model"], f.get("file", ""), cwe)
        groups[key].append(f)

    deduped = []
    for key, group in groups.items():
        model = key[0]
        file_path = key[1]

        # Collect tools
        tools = sorted(set(f["_tool"] for f in group))

        # Take highest severity
        sev = highest_severity(*(f.get("severity", "LOW") for f in group))

        # Take lowest line number (most relevant location)
        lines = [f.get("line", 0) for f in group if f.get("line", 0) > 0]
        line = min(lines) if lines else 0

        # CWE: use the key CWE or first from group
        cwe = key[2] if not key[2].startswith("_nocwe_") else group[0].get("cwe", "")

        # OWASP: take first non-empty
        owasp = ""
        for f in group:
            if f.get("owasp", "") and f["owasp"] != "unknown":
                owasp = f["owasp"]
                break

        deduped.append({
            "model": model,
            "file": file_path,
            "line": line,
            "cwe": cwe,
            "owasp": owasp,
            "severity": sev,
            "tools": ", ".join(tools),
        })

    return deduped


def sort_findings(findings):
    """Sort by model, then OWASP category, then file path."""
    def sort_key(f):
        return (
            f.get("model", ""),
            f.get("owasp", "Z99"),  # unknowns sort last
            f.get("file", ""),
            f.get("line", 0),
        )
    return sorted(findings, key=sort_key)


def assign_ids(findings):
    """Assign sequential finding IDs (F001, F002, ...)."""
    for i, f in enumerate(findings, start=1):
        f["finding_id"] = f"F{i:03d}"
    return findings


def write_csv(findings, output_path):
    """Write findings to CSV with the standard column set."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for finding in findings:
            row = {
                "finding_id": finding.get("finding_id", ""),
                "model": finding.get("model", ""),
                "file": finding.get("file", ""),
                "line": finding.get("line", 0),
                "cwe": finding.get("cwe", ""),
                "owasp": finding.get("owasp", ""),
                "severity": finding.get("severity", ""),
                "tools": finding.get("tools", ""),
                "validated": "",
                "notes": "",
            }
            writer.writerow(row)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Generate a validation CSV from scan results. "
            "Deduplicates findings (same file + CWE from multiple tools = one row) "
            "and produces a template for manual TP/FP review."
        )
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output CSV path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Process only this model ID (e.g. gpt-5.2)",
    )
    parser.add_argument(
        "--scans-dir",
        type=Path,
        default=SCANS_DIR,
        help=f"Scans directory (default: {SCANS_DIR})",
    )
    args = parser.parse_args()

    print("Validation Template Generator")
    print("=" * 50)

    # Load raw findings
    print(f"Scanning: {args.scans_dir}")
    raw_findings = load_scan_results(args.scans_dir, model_filter=args.model)

    if not raw_findings:
        print("No scan results found.")
        print(f"  Looked in: {args.scans_dir}")
        print("  Expected structure: scans/{model_id}/{tool}.json")
        print("  Run scan.py first to generate scan results.")
        sys.exit(0)

    print(f"Raw findings loaded: {len(raw_findings)}")

    # Count by model before dedup
    model_counts = defaultdict(int)
    for f in raw_findings:
        model_counts[f["_model"]] += 1
    for model_id, count in sorted(model_counts.items()):
        print(f"  {model_id}: {count} raw findings")

    # Deduplicate
    deduped = deduplicate_findings(raw_findings)
    print(f"\nAfter deduplication: {len(deduped)} unique findings")
    print(f"  Removed {len(raw_findings) - len(deduped)} duplicates")

    # Sort and assign IDs
    deduped = sort_findings(deduped)
    deduped = assign_ids(deduped)

    # Write CSV
    write_csv(deduped, args.output)
    print(f"\nWrote: {args.output}")
    print(f"Columns: {', '.join(CSV_COLUMNS)}")
    print("\nNext step: Open the CSV and fill in the 'validated' column")
    print("  TP = True Positive (real vulnerability)")
    print("  FP = False Positive (not a real vulnerability)")
    print("  UNCLEAR = Needs further analysis")


if __name__ == "__main__":
    main()
