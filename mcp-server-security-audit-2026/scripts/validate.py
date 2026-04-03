#!/usr/bin/env python3
"""
Validation CSV Generator
MCP Server Security Audit 2026

Reads scan results, deduplicates findings, and generates a CSV for manual review.
"""

import csv
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parent.parent
SCANS_DIR = STUDY_DIR / "scans"
INVENTORY = STUDY_DIR / "inventory" / "selected-100.json"
OUTPUT = STUDY_DIR / "data" / "validation.csv"

CSV_COLUMNS = [
    "finding_id", "server", "server_category", "finding_type",
    "severity", "tool_name", "description", "details", "scanners",
    "validated", "notes",
]


def load_servers():
    with open(INVENTORY) as f:
        return {s["name"]: s for s in json.load(f)}


def load_scan_results():
    findings = []
    for server_dir in sorted(SCANS_DIR.iterdir()):
        if not server_dir.is_dir():
            continue
        for scan_file in server_dir.glob("*.json"):
            with open(scan_file) as f:
                data = json.load(f)
            server_name = data.get("server", server_dir.name)
            for finding in data.get("findings", []):
                finding["_server"] = server_name
                finding["_scanner"] = data.get("scanner", scan_file.stem)
                findings.append(finding)
    return findings


def deduplicate(findings):
    groups = defaultdict(list)
    for f in findings:
        key = (f["_server"], f.get("type", ""), f.get("tool_name", ""))
        groups[key].append(f)

    deduped = []
    for key, group in groups.items():
        scanners = sorted(set(f["_scanner"] for f in group))
        best_sev = "LOW"
        sev_rank = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
        for f in group:
            if sev_rank.get(f.get("severity", "LOW"), 0) > sev_rank.get(best_sev, 0):
                best_sev = f.get("severity", "LOW")

        deduped.append({
            "server": key[0],
            "finding_type": key[1],
            "tool_name": key[2],
            "severity": best_sev,
            "description": group[0].get("description", ""),
            "details": group[0].get("details", ""),
            "scanners": ", ".join(scanners),
        })
    return deduped


def main():
    servers = load_servers()
    raw = load_scan_results()
    print(f"Raw findings: {len(raw)}")

    deduped = deduplicate(raw)
    deduped.sort(key=lambda f: (f["server"], f["severity"], f["finding_type"]))
    print(f"After dedup: {len(deduped)}")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for i, finding in enumerate(deduped, 1):
            srv = servers.get(finding["server"], {})
            writer.writerow({
                "finding_id": f"M{i:03d}",
                "server": finding["server"],
                "server_category": srv.get("category", "unknown"),
                "finding_type": finding["finding_type"],
                "severity": finding["severity"],
                "tool_name": finding.get("tool_name", ""),
                "description": finding["description"],
                "details": finding["details"],
                "scanners": finding["scanners"],
                "validated": "",
                "notes": "",
            })

    print(f"Output: {OUTPUT}")

    sev_counts = Counter(f["severity"] for f in deduped)
    type_counts = Counter(f["finding_type"] for f in deduped)
    print(f"\nBy severity: {dict(sev_counts)}")
    print(f"By type: {dict(type_counts)}")


if __name__ == "__main__":
    main()
