#!/usr/bin/env python3
"""Calculate F-measure metrics (Precision, Recall, F1-Score) from triage results
and ground truth data.

Reads triage CSV files and ground truth CSVs, then produces:
  1. metrics/fmeasure-summary.csv  — per tool x per target P/R/F1
  2. metrics/cwe-coverage.csv      — per tool x per CWE detection coverage
  3. metrics/tool-scorecard.csv    — aggregated per-tool scorecard
  4. Stdout summary table

Usage:
    python3 calculate-fmeasure.py <triage-dir> <ground-truth-dir> <output-dir> [speed-file]
"""

import csv
import sys
import os
from pathlib import Path
from collections import defaultdict


def load_triage_files(triage_dir):
    """Load all triage CSVs. Prefer *-final.csv, fall back to *-auto.csv.

    Returns dict: target -> list of row dicts.
    """
    triage_dir = Path(triage_dir)
    if not triage_dir.is_dir():
        print(f"Error: triage directory not found: {triage_dir}", file=sys.stderr)
        sys.exit(1)

    # Discover available files per target
    auto_files = {}
    final_files = {}

    for f in sorted(triage_dir.glob("*.csv")):
        name = f.stem
        if name.endswith("-final"):
            target = name.rsplit("-final", 1)[0]
            final_files[target] = f
        elif name.endswith("-auto"):
            target = name.rsplit("-auto", 1)[0]
            auto_files[target] = f

    # Prefer final over auto
    chosen = {}
    all_targets = set(auto_files.keys()) | set(final_files.keys())
    for target in all_targets:
        if target in final_files:
            chosen[target] = final_files[target]
        elif target in auto_files:
            chosen[target] = auto_files[target]

    if not chosen:
        print(f"Warning: no triage CSV files found in {triage_dir}", file=sys.stderr)
        return {}

    results = {}
    for target, filepath in sorted(chosen.items()):
        rows = []
        with open(filepath, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                row["_target"] = target
                rows.append(row)
        results[target] = rows
        print(f"  Loaded {len(rows)} findings from {filepath.name} ({target})")

    return results


def load_ground_truth(gt_dir):
    """Load ground truth CSVs.

    Returns dict: target -> list of row dicts with keys from CSV headers.
    """
    gt_dir = Path(gt_dir)
    if not gt_dir.is_dir():
        print(f"Error: ground truth directory not found: {gt_dir}", file=sys.stderr)
        sys.exit(1)

    results = {}
    for f in sorted(gt_dir.glob("*.csv")):
        target = f.stem
        rows = []
        with open(f, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                rows.append(row)
        results[target] = rows
        print(f"  Loaded {len(rows)} ground truth entries for {target}")

    if not results:
        print(f"Warning: no ground truth CSV files found in {gt_dir}", file=sys.stderr)

    return results


def load_speed_data(speed_file):
    """Load optional scan duration data.

    Expects CSV with columns: tool, target, duration_seconds
    Returns dict: (tool, target) -> duration_seconds (float).
    """
    if not speed_file or not Path(speed_file).is_file():
        return {}

    data = {}
    with open(speed_file, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            tool = row.get("tool", "").strip().lower()
            target = row.get("target", "").strip()
            try:
                duration = float(row.get("duration_seconds", 0))
            except (ValueError, TypeError):
                duration = 0.0
            if tool and target:
                data[(tool, target)] = duration

    return data


def extract_tool_findings(triage_data):
    """From grouped triage data, extract per-tool findings.

    Each triage row has a 'tools' column (comma-separated tool names).
    A TP for tools='bearer,zap' means both bearer and zap get credit for that TP.
    An FP for tools='nodejsscan' means only nodejsscan gets that FP.

    Returns dict: (tool, target) -> {"tp": int, "fp": int, "tp_cwes": set}
    """
    tool_stats = defaultdict(lambda: {"tp": 0, "fp": 0, "tp_cwes": set()})

    for target, rows in triage_data.items():
        for row in rows:
            tools_str = row.get("tools", "").strip()
            if not tools_str:
                continue

            tools = [t.strip().lower() for t in tools_str.split(",") if t.strip()]
            verdict = row.get("verdict", "").strip().upper()
            cwe = row.get("cwe", "").strip()

            for tool in tools:
                key = (tool, target)
                if verdict == "TP":
                    tool_stats[key]["tp"] += 1
                    if cwe:
                        tool_stats[key]["tp_cwes"].add(cwe)
                elif verdict == "FP":
                    tool_stats[key]["fp"] += 1

    return tool_stats


def calculate_fmeasure(tool_findings, ground_truth, speed_data):
    """Calculate Precision, Recall, F1 per tool per target.

    FN = ground truth entries whose CWE was NOT found as TP by this tool on this target.
    We count at the CWE level: for each unique CWE in ground truth, if the tool found
    at least one TP with that CWE, those GT entries are "covered"; otherwise they are FN.

    Returns list of dicts for CSV output, sorted by (tool, target).
    """
    results = []

    # Collect all (tool, target) pairs
    all_tools = set()
    for tool, target in tool_findings:
        all_tools.add(tool)

    # Also gather all targets from ground truth
    all_targets = set(ground_truth.keys())

    for tool in sorted(all_tools):
        for target in sorted(all_targets):
            key = (tool, target)
            stats = tool_findings.get(key)

            if stats is None:
                # Tool didn't scan this target — skip
                continue

            tp = stats["tp"]
            fp = stats["fp"]
            tp_cwes = stats["tp_cwes"]

            # Count FN: ground truth entries whose CWE was not found by this tool
            gt_entries = ground_truth.get(target, [])
            fn = 0
            for gt_row in gt_entries:
                gt_cwe = gt_row.get("cwe", "").strip()
                if gt_cwe not in tp_cwes:
                    fn += 1

            total_findings = tp + fp

            # Calculate metrics
            precision = round(tp / (tp + fp), 3) if (tp + fp) > 0 else 0.0
            recall = round(tp / (tp + fn), 3) if (tp + fn) > 0 else 0.0
            f1 = round(2 * precision * recall / (precision + recall), 3) if (precision + recall) > 0 else 0.0

            duration = speed_data.get((tool, target), "")

            results.append({
                "tool": tool,
                "target": target,
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "total_findings": total_findings,
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "scan_duration_seconds": duration,
            })

    # Sort by F1 descending, then tool name
    results.sort(key=lambda r: (-r["f1"], r["tool"], r["target"]))

    return results


def calculate_cwe_coverage(tool_findings, ground_truth):
    """Calculate per-tool per-CWE detection coverage.

    For each CWE in ground truth, check if this tool found it (TP) on that target.

    Returns list of dicts for CSV output.
    """
    # Build a map of all CWEs in ground truth across all targets
    # Structure: cwe -> list of (target, gt_row)
    gt_by_cwe = defaultdict(list)
    for target, gt_rows in ground_truth.items():
        for row in gt_rows:
            cwe = row.get("cwe", "").strip()
            if cwe:
                gt_by_cwe[cwe].append(target)

    # Collect all tools
    all_tools = set()
    for tool, target in tool_findings:
        all_tools.add(tool)

    results = []

    for tool in sorted(all_tools):
        # Gather all TP CWEs per target for this tool
        tool_tp_cwes_by_target = defaultdict(set)
        for (t, target), stats in tool_findings.items():
            if t == tool:
                tool_tp_cwes_by_target[target] = stats["tp_cwes"]

        for cwe in sorted(gt_by_cwe.keys()):
            targets_with_cwe = gt_by_cwe[cwe]
            total = len(targets_with_cwe)

            found = 0
            for target in targets_with_cwe:
                if cwe in tool_tp_cwes_by_target.get(target, set()):
                    found += 1

            missed = total - found
            coverage_pct = round(found / total * 100, 1) if total > 0 else 0.0

            results.append({
                "tool": tool,
                "cwe": cwe,
                "found_count": found,
                "missed_count": missed,
                "total_in_ground_truth": total,
                "coverage_pct": coverage_pct,
            })

    return results


def calculate_scorecard(fmeasure_results, cwe_coverage):
    """Aggregate F-measure results across targets for per-tool scorecard.

    Returns list of dicts sorted by avg_f1 descending.
    """
    # Group fmeasure results by tool
    tool_data = defaultdict(list)
    for row in fmeasure_results:
        tool_data[row["tool"]].append(row)

    # Get unique CWEs found per tool from coverage data
    tool_cwes = defaultdict(set)
    for row in cwe_coverage:
        if row["found_count"] > 0:
            tool_cwes[row["tool"]].add(row["cwe"])

    results = []
    for tool, rows in tool_data.items():
        n = len(rows)
        avg_precision = round(sum(r["precision"] for r in rows) / n, 3) if n > 0 else 0.0
        avg_recall = round(sum(r["recall"] for r in rows) / n, 3) if n > 0 else 0.0
        avg_f1 = round(sum(r["f1"] for r in rows) / n, 3) if n > 0 else 0.0
        total_tp = sum(r["tp"] for r in rows)
        total_fp = sum(r["fp"] for r in rows)
        total_fn = sum(r["fn"] for r in rows)
        unique_cwes = len(tool_cwes.get(tool, set()))

        results.append({
            "tool": tool,
            "avg_precision": avg_precision,
            "avg_recall": avg_recall,
            "avg_f1": avg_f1,
            "total_tp": total_tp,
            "total_fp": total_fp,
            "total_fn": total_fn,
            "targets_scanned": n,
            "unique_cwes_found": unique_cwes,
        })

    results.sort(key=lambda r: (-r["avg_f1"], r["tool"]))
    return results


def write_csv(filepath, rows, fieldnames):
    """Write a list of dicts to CSV."""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    with open(filepath, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"  Wrote {len(rows)} rows to {filepath}")


def print_summary(scorecard):
    """Pretty-print the tool scorecard summary table."""
    if not scorecard:
        print("\nNo results to display.")
        return

    # Header
    header = (
        f"{'Tool':<20} | {'Targets':>7} | {'Avg F1':>6} | {'Avg P':>6} | "
        f"{'Avg R':>6} | {'TP':>5} | {'FP':>5} | {'CWEs':>4}"
    )
    separator = "-" * len(header)

    print(f"\n{header}")
    print(separator)

    for row in scorecard:
        print(
            f"{row['tool']:<20} | {row['targets_scanned']:>7} | "
            f"{row['avg_f1']:>6.3f} | {row['avg_precision']:>6.3f} | "
            f"{row['avg_recall']:>6.3f} | {row['total_tp']:>5} | "
            f"{row['total_fp']:>5} | {row['unique_cwes_found']:>4}"
        )

    print(separator)
    print(f"  {len(scorecard)} tools evaluated\n")


def main():
    triage_dir = sys.argv[1] if len(sys.argv) > 1 else "triage"
    gt_dir = sys.argv[2] if len(sys.argv) > 2 else "ground-truth"
    output_dir = sys.argv[3] if len(sys.argv) > 3 else "metrics"
    speed_file = sys.argv[4] if len(sys.argv) > 4 else None

    print("=== CandyShop Benchmark — F-Measure Calculator ===\n")

    # Load data
    print("Loading triage files...")
    triage_data = load_triage_files(triage_dir)
    if not triage_data:
        print("No triage data found. Nothing to calculate.", file=sys.stderr)
        sys.exit(1)

    print("\nLoading ground truth...")
    ground_truth = load_ground_truth(gt_dir)
    if not ground_truth:
        print("No ground truth data found. Nothing to calculate.", file=sys.stderr)
        sys.exit(1)

    print("\nLoading speed data...")
    speed_data = load_speed_data(speed_file)
    if speed_data:
        print(f"  Loaded {len(speed_data)} duration entries")
    else:
        print("  No speed data (optional)")

    # Extract per-tool findings from triage
    print("\nExtracting per-tool findings...")
    tool_findings = extract_tool_findings(triage_data)
    tools_found = sorted(set(t for t, _ in tool_findings.keys()))
    targets_found = sorted(set(tgt for _, tgt in tool_findings.keys()))
    print(f"  {len(tools_found)} tools: {', '.join(tools_found)}")
    print(f"  {len(targets_found)} targets: {', '.join(targets_found)}")

    # Calculate metrics
    print("\nCalculating F-measure...")
    fmeasure = calculate_fmeasure(tool_findings, ground_truth, speed_data)

    print("Calculating CWE coverage...")
    cwe_coverage = calculate_cwe_coverage(tool_findings, ground_truth)

    print("Calculating tool scorecard...")
    scorecard = calculate_scorecard(fmeasure, cwe_coverage)

    # Write output CSVs
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("\nWriting output files...")

    write_csv(
        output_dir / "fmeasure-summary.csv",
        fmeasure,
        ["tool", "target", "tp", "fp", "fn", "total_findings",
         "precision", "recall", "f1", "scan_duration_seconds"],
    )

    write_csv(
        output_dir / "cwe-coverage.csv",
        cwe_coverage,
        ["tool", "cwe", "found_count", "missed_count",
         "total_in_ground_truth", "coverage_pct"],
    )

    write_csv(
        output_dir / "tool-scorecard.csv",
        scorecard,
        ["tool", "avg_precision", "avg_recall", "avg_f1",
         "total_tp", "total_fp", "total_fn", "targets_scanned",
         "unique_cwes_found"],
    )

    # Print summary
    print_summary(scorecard)


if __name__ == "__main__":
    main()
