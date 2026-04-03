#!/usr/bin/env python3
"""
Aggregation Script
MCP Server Security Audit 2026

Reads runtime_validation.csv (TP findings only) and produces
hugo-site/data/mcp_audit_2026.json for the published article.
"""

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parent.parent
VALIDATION_CSV = STUDY_DIR / "data" / "runtime_validation.csv"
RUNTIME_JSON = STUDY_DIR / "data" / "runtime_scan_results.json"
SELECTED = STUDY_DIR / "inventory" / "selected-100.json"
OUTPUT = Path("/Users/suphi/appsecsanta/hugo-site/data/mcp_audit_2026.json")


def main():
    with open(VALIDATION_CSV) as f:
        all_rows = list(csv.DictReader(f))

    with open(RUNTIME_JSON) as f:
        runtime = json.load(f)

    with open(SELECTED) as f:
        servers = {s["name"]: s for s in json.load(f)}

    tp_rows = [r for r in all_rows if r["validated"] == "TP"]
    fp_rows = [r for r in all_rows if r["validated"] == "FP"]

    connected = [r for r in runtime["results"] if not r.get("error")]
    total_tools = sum(r["tools_count"] for r in connected)

    tp_servers = set(r["server"] for r in tp_rows)

    by_category = {}
    cat_servers = Counter(r.get("category", "unknown") for r in connected)
    cat_tp_servers = defaultdict(set)
    cat_findings = Counter()
    for r in tp_rows:
        cat = r["category"]
        cat_tp_servers[cat].add(r["server"])
        cat_findings[cat] += 1

    for cat in sorted(cat_servers.keys()):
        by_category[cat] = {
            "servers_scanned": cat_servers[cat],
            "servers_with_findings": len(cat_tp_servers.get(cat, set())),
            "total_findings": cat_findings.get(cat, 0),
            "vuln_rate": round(len(cat_tp_servers.get(cat, set())) / cat_servers[cat] * 100, 1) if cat_servers[cat] > 0 else 0,
        }

    by_finding_type = {}
    type_counts = Counter(r["type"] for r in tp_rows)
    for ftype, count in type_counts.most_common():
        by_finding_type[ftype] = {
            "count": count,
            "severity": tp_rows[[r["type"] for r in tp_rows].index(ftype)]["severity"],
            "servers_affected": len(set(r["server"] for r in tp_rows if r["type"] == ftype)),
        }

    by_severity = dict(Counter(r["severity"] for r in tp_rows))

    top_servers = []
    srv_counts = Counter(r["server"] for r in tp_rows)
    for srv, count in srv_counts.most_common(10):
        srv_info = servers.get(srv, {})
        srv_runtime = next((r for r in connected if r["server"] == srv), {})
        top_servers.append({
            "name": srv,
            "category": srv_info.get("category", "unknown"),
            "findings": count,
            "tools_count": srv_runtime.get("tools_count", 0),
        })

    result = {
        "metadata": {
            "total_servers_selected": len(servers),
            "total_servers_connected": len(connected),
            "connection_errors": len(runtime["results"]) - len(connected),
            "total_tools_discovered": total_tools,
            "avg_tools_per_server": round(total_tools / len(connected), 1) if connected else 0,
            "total_findings_raw": len(all_rows),
            "total_findings_tp": len(tp_rows),
            "total_findings_fp": len(fp_rows),
            "servers_with_findings": len(tp_servers),
            "vuln_rate": round(len(tp_servers) / len(connected) * 100, 1) if connected else 0,
            "scan_date": runtime.get("scan_date", "2026-04-03"),
            "scanners": ["mcp-scan", "runtime-tool-analysis"],
        },
        "by_category": by_category,
        "by_finding_type": by_finding_type,
        "by_severity": by_severity,
        "top_servers": top_servers,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w") as f:
        json.dump(result, f, indent=2)

    print("MCP Audit Aggregation")
    print("=" * 50)
    m = result["metadata"]
    print(f"Servers: {m['total_servers_connected']}/{m['total_servers_selected']} connected")
    print(f"Tools: {m['total_tools_discovered']}")
    print(f"Findings: {m['total_findings_tp']} TP / {m['total_findings_fp']} FP")
    print(f"Vuln rate: {m['vuln_rate']}% ({m['servers_with_findings']}/{m['total_servers_connected']})")
    print(f"\nOutput: {OUTPUT}")


if __name__ == "__main__":
    main()
