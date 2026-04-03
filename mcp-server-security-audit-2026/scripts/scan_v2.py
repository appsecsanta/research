#!/usr/bin/env python3
"""
MCP Server Security Scanner v2
MCP Server Security Audit 2026

Uses 2 established OSS scanners — no custom analysis:
    1. mcp-scan v2.0.1 (Snyk/Invariant) — static config analysis
    2. cisco-ai-mcp-scanner v4.3.0 (Cisco AI Defense) — YARA + runtime tool analysis

Usage:
    python3 scan_v2.py                        # Scan all servers
    python3 scan_v2.py --limit 5              # Test with 5
    python3 scan_v2.py --scanner cisco        # One scanner only
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
STUDY_DIR = SCRIPT_DIR.parent
SELECTED = STUDY_DIR / "inventory" / "selected-100.json"
SCANS_DIR = STUDY_DIR / "scans_v2"
VENV312 = STUDY_DIR / "venv312" / "bin"

TIMEOUT = 90


def load_servers():
    with open(SELECTED) as f:
        return json.load(f)


def run_mcp_scan(server, server_dir):
    npm_pkg = server.get("npm_package", "")
    if not npm_pkg:
        return {"scanner": "mcp-scan", "server": server["name"], "findings": [], "error": "No npm package"}

    tmpdir = tempfile.mkdtemp(prefix="mcpscan_")
    try:
        config = {"mcpServers": {"target": {"command": "npx", "args": ["-y", npm_pkg]}}}
        config_path = Path(tmpdir) / "mcp.json"
        config_path.write_text(json.dumps(config))

        result = subprocess.run(
            ["mcp-scan", "scan", "-c", str(config_path), "--json"],
            capture_output=True, text=True, timeout=TIMEOUT,
        )

        stdout = result.stdout.strip()
        if not stdout:
            return {"scanner": "mcp-scan", "server": server["name"], "findings": [], "error": result.stderr.strip()[:200]}

        data = json.loads(stdout)
        findings = []
        for entry in data.get("results", []):
            for f in entry.get("findings", []):
                if f.get("id") == "unverified-source":
                    continue  # skip noise
                findings.append({
                    "type": f.get("id", "unknown"),
                    "severity": f.get("severity", "MEDIUM").upper(),
                    "description": f.get("description", ""),
                    "recommendation": f.get("fixRecommendation", ""),
                })

        return {
            "scanner": "mcp-scan",
            "server": server["name"],
            "findings": findings,
            "trust_score": data.get("results", [{}])[0].get("trustScore") if data.get("results") else None,
            "metadata": data.get("results", [{}])[0].get("metadata", {}) if data.get("results") else {},
        }
    except subprocess.TimeoutExpired:
        return {"scanner": "mcp-scan", "server": server["name"], "findings": [], "error": f"Timeout ({TIMEOUT}s)"}
    except (json.JSONDecodeError, FileNotFoundError) as e:
        return {"scanner": "mcp-scan", "server": server["name"], "findings": [], "error": str(e)[:200]}
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def run_cisco_scanner(server, server_dir):
    npm_pkg = server.get("npm_package", "")
    if not npm_pkg:
        return {"scanner": "cisco-mcp-scanner", "server": server["name"], "findings": [], "tools_scanned": 0, "error": "No npm package"}

    scanner = str(VENV312 / "mcp-scanner")
    stderr_file = str(server_dir / "cisco_stderr.log")

    cmd = [
        scanner,
        "--analyzers", "yara",
        "--format", "raw",
        "--raw",
        "stdio",
        "--stdio-command", "npx",
        "--stdio-arg=-y",
        f"--stdio-arg={npm_pkg}",
        "--stderr-file", stderr_file,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
        stdout = result.stdout.strip()

        if not stdout:
            return {"scanner": "cisco-mcp-scanner", "server": server["name"], "findings": [], "tools_scanned": 0, "error": result.stderr.strip()[:200]}

        data = json.loads(stdout)
        if not isinstance(data, list):
            data = [data]

        findings = []
        tools_scanned = len(data)
        safe_count = 0

        for tool_result in data:
            is_safe = tool_result.get("is_safe", True)
            tool_name = tool_result.get("tool_name", "")

            if is_safe:
                safe_count += 1
                continue

            for analyzer_name, analyzer_result in tool_result.get("findings", {}).items():
                if analyzer_result.get("severity", "SAFE") == "SAFE":
                    continue
                for threat in analyzer_result.get("threat_names", []):
                    findings.append({
                        "type": threat,
                        "severity": analyzer_result.get("severity", "MEDIUM").upper(),
                        "description": analyzer_result.get("threat_summary", ""),
                        "tool_name": tool_name,
                        "tool_description": tool_result.get("tool_description", "")[:300],
                        "analyzer": analyzer_name,
                    })

        return {
            "scanner": "cisco-mcp-scanner",
            "server": server["name"],
            "findings": findings,
            "tools_scanned": tools_scanned,
            "tools_safe": safe_count,
            "tools_unsafe": tools_scanned - safe_count,
        }
    except subprocess.TimeoutExpired:
        return {"scanner": "cisco-mcp-scanner", "server": server["name"], "findings": [], "tools_scanned": 0, "error": f"Timeout ({TIMEOUT}s)"}
    except (json.JSONDecodeError, FileNotFoundError) as e:
        return {"scanner": "cisco-mcp-scanner", "server": server["name"], "findings": [], "tools_scanned": 0, "error": str(e)[:200]}


def main():
    parser = argparse.ArgumentParser(description="Scan MCP servers with OSS security tools.")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--scanner", choices=["mcp-scan", "cisco", "all"], default="all")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    servers = load_servers()
    scannable = [s for s in servers if s.get("npm_package")]
    if args.limit > 0:
        scannable = scannable[:args.limit]

    print(f"MCP Server Security Scanner v2")
    print(f"=" * 50)
    print(f"Servers: {len(scannable)} (scannable via npm)")
    print(f"Scanners: {args.scanner}")

    if args.dry_run:
        for s in scannable:
            print(f"  {s['name']} ({s['category']})")
        return

    print("-" * 50)

    all_results = []
    for i, server in enumerate(scannable, 1):
        slug = server["name"].replace("/", "-").replace("@", "").lower()
        server_dir = SCANS_DIR / slug
        server_dir.mkdir(parents=True, exist_ok=True)

        print(f"[{i}/{len(scannable)}] {server['name']}", end="", flush=True)

        server_result = {"server": server["name"], "category": server.get("category", "unknown")}

        if args.scanner in ("all", "mcp-scan"):
            start = time.time()
            ms_result = run_mcp_scan(server, server_dir)
            ms_time = time.time() - start
            with open(server_dir / "mcp_scan.json", "w") as f:
                json.dump(ms_result, f, indent=2)
            server_result["mcp_scan"] = ms_result
            ms_findings = len(ms_result.get("findings", []))
            ms_err = " ERR" if ms_result.get("error") else ""
            print(f" | mcp-scan: {ms_findings}f {ms_time:.0f}s{ms_err}", end="", flush=True)

        if args.scanner in ("all", "cisco"):
            start = time.time()
            cisco_result = run_cisco_scanner(server, server_dir)
            cisco_time = time.time() - start
            with open(server_dir / "cisco_scanner.json", "w") as f:
                json.dump(cisco_result, f, indent=2)
            server_result["cisco_scanner"] = cisco_result
            cisco_findings = len(cisco_result.get("findings", []))
            cisco_tools = cisco_result.get("tools_scanned", 0)
            cisco_err = " ERR" if cisco_result.get("error") else ""
            print(f" | cisco: {cisco_findings}f/{cisco_tools}t {cisco_time:.0f}s{cisco_err}", end="", flush=True)

        print()
        all_results.append(server_result)

    # Summary
    print("-" * 50)
    total_mcp_findings = sum(len(r.get("mcp_scan", {}).get("findings", [])) for r in all_results)
    total_cisco_findings = sum(len(r.get("cisco_scanner", {}).get("findings", [])) for r in all_results)
    total_tools = sum(r.get("cisco_scanner", {}).get("tools_scanned", 0) for r in all_results)
    cisco_connected = sum(1 for r in all_results if r.get("cisco_scanner", {}).get("tools_scanned", 0) > 0)

    print(f"mcp-scan findings: {total_mcp_findings}")
    print(f"cisco-scanner: {cisco_connected} connected, {total_tools} tools, {total_cisco_findings} findings")

    combined_path = STUDY_DIR / "data" / "scan_v2_results.json"
    combined_path.parent.mkdir(parents=True, exist_ok=True)
    with open(combined_path, "w") as f:
        json.dump({"scan_date": time.strftime("%Y-%m-%d"), "results": all_results}, f, indent=2)
    print(f"Output: {combined_path}")


if __name__ == "__main__":
    main()
