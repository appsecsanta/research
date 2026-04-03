#!/usr/bin/env python3
"""
MCP Server Security Scanner
MCP Server Security Audit 2026

Runs 2 security scanners against each selected MCP server:
    1. mcp-scan (npm global) — prompt injection, tool poisoning, toxic flows
    2. defenseclaw mcp scan (Python) — MCP scanner + CodeGuard static analysis

For each server, creates a temporary MCP config, runs both scanners,
and saves normalized JSON results.

Usage:
    python3 scan.py                          # Scan all 100 servers
    python3 scan.py --server context7        # Scan one server
    python3 scan.py --scanner mcp-scan       # Use one scanner only
    python3 scan.py --dry-run                # Preview without scanning
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
SCANS_DIR = STUDY_DIR / "scans"
VENV_ACTIVATE = STUDY_DIR / "venv312" / "bin" / "activate"

TIMEOUT_DEFAULT = 120
ALL_SCANNERS = ["mcp-scan", "defenseclaw"]


def load_servers():
    with open(SELECTED) as f:
        return json.load(f)


def make_mcp_config(server, tmpdir):
    name = server["name"].replace("/", "-").replace("@", "")
    install_cmd = server.get("install_command", "")
    npm_pkg = server.get("npm_package", "")

    if npm_pkg:
        command = "npx"
        args = ["-y", npm_pkg]
    elif install_cmd:
        parts = install_cmd.split()
        command = parts[0]
        args = parts[1:]
    else:
        return None

    config = {
        "mcpServers": {
            name: {
                "command": command,
                "args": args,
            }
        }
    }

    config_path = Path(tmpdir) / "mcp.json"
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    return config_path


def run_mcp_scan(server, config_path, output_dir):
    cmd = [
        "mcp-scan", "scan",
        "-c", str(config_path),
        "--json",
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=TIMEOUT_DEFAULT
        )
        stdout = result.stdout.strip()
        if not stdout:
            return {"scanner": "mcp-scan", "server": server["name"], "findings": [], "error": result.stderr.strip()[:500]}

        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            return {"scanner": "mcp-scan", "server": server["name"], "findings": [], "error": f"JSON parse error: {stdout[:200]}"}

        findings = []
        for result_entry in data.get("results", []):
            server_name = result_entry.get("serverName", "")
            for finding in result_entry.get("findings", []):
                findings.append({
                    "type": finding.get("id", "unknown"),
                    "severity": finding.get("severity", "MEDIUM").upper(),
                    "description": finding.get("description", ""),
                    "tool_name": result_entry.get("toolName", server_name),
                    "details": finding.get("fixRecommendation", ""),
                    "fixable": finding.get("fixable", False),
                })

        summary = {
            "critical": data.get("criticalCount", 0),
            "high": data.get("highCount", 0),
            "medium": data.get("mediumCount", 0),
            "low": data.get("lowCount", 0),
        }

        return {"scanner": "mcp-scan", "server": server["name"], "findings": findings, "raw_count": len(findings), "summary": summary}

    except subprocess.TimeoutExpired:
        return {"scanner": "mcp-scan", "server": server["name"], "findings": [], "error": f"Timeout after {TIMEOUT_DEFAULT}s"}
    except FileNotFoundError:
        return {"scanner": "mcp-scan", "server": server["name"], "findings": [], "error": "mcp-scan not found"}


def run_defenseclaw(server, config_path, output_dir):
    activate = str(VENV_ACTIVATE)
    cmd_str = f"source {activate} && defenseclaw mcp scan --json --scan-prompts --scan-resources --scan-instructions {server['name']}"

    # DefenseClaw needs the config in openclaw format — create a temp one
    tmpdir = tempfile.mkdtemp(prefix="dclaw_")
    try:
        # Read the mcp config and convert to openclaw format
        with open(config_path) as f:
            mcp_config = json.load(f)

        openclaw_config = {"mcp_servers": mcp_config.get("mcpServers", {})}
        openclaw_path = Path(tmpdir) / "openclaw.json"
        with open(openclaw_path, "w") as f:
            json.dump(openclaw_config, f, indent=2)

        env = dict(os.environ)
        env["OPENCLAW_CONFIG"] = str(openclaw_path)

        server_name = list(mcp_config.get("mcpServers", {}).keys())[0] if mcp_config.get("mcpServers") else server["name"]

        cmd = [
            "bash", "-c",
            f"source {activate} && defenseclaw mcp scan --json --scan-prompts --scan-resources --scan-instructions '{server_name}'"
        ]

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=TIMEOUT_DEFAULT, env=env
        )

        stdout = result.stdout.strip()
        if not stdout:
            return {"scanner": "defenseclaw", "server": server["name"], "findings": [], "error": result.stderr.strip()[:500]}

        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            return {"scanner": "defenseclaw", "server": server["name"], "findings": [], "error": f"JSON parse error: {stdout[:200]}"}

        findings = []
        for finding in data if isinstance(data, list) else data.get("findings", data.get("results", [])):
            if isinstance(finding, dict):
                findings.append({
                    "type": finding.get("type", finding.get("category", "unknown")),
                    "severity": finding.get("severity", "MEDIUM").upper(),
                    "description": finding.get("description", finding.get("message", "")),
                    "tool_name": finding.get("tool_name", finding.get("toolName", "")),
                    "details": finding.get("details", finding.get("recommendation", "")),
                })

        return {"scanner": "defenseclaw", "server": server["name"], "findings": findings, "raw_count": len(findings)}

    except subprocess.TimeoutExpired:
        return {"scanner": "defenseclaw", "server": server["name"], "findings": [], "error": f"Timeout after {TIMEOUT_DEFAULT}s"}
    except FileNotFoundError:
        return {"scanner": "defenseclaw", "server": server["name"], "findings": [], "error": "defenseclaw not found"}
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


SCANNER_RUNNERS = {
    "mcp-scan": run_mcp_scan,
    "defenseclaw": run_defenseclaw,
}


def main():
    parser = argparse.ArgumentParser(description="Scan MCP servers with security tools.")
    parser.add_argument("--server", type=str, help="Scan only this server (by name)")
    parser.add_argument("--scanner", choices=ALL_SCANNERS, help="Use only this scanner")
    parser.add_argument("--dry-run", action="store_true", help="Preview without scanning")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of servers to scan")
    args = parser.parse_args()

    print("MCP Server Security Scanner")
    print("=" * 50)

    servers = load_servers()
    if args.server:
        servers = [s for s in servers if s["name"] == args.server or args.server in s["name"]]
        if not servers:
            print(f"Server '{args.server}' not found")
            sys.exit(1)

    if args.limit > 0:
        servers = servers[:args.limit]

    scanners = ALL_SCANNERS
    if args.scanner:
        scanners = [args.scanner]

    print(f"Servers: {len(servers)}")
    print(f"Scanners: {', '.join(scanners)}")
    print(f"Output: {SCANS_DIR}")

    if args.dry_run:
        for s in servers:
            print(f"  {s['name']} ({s['category']})")
        print(f"\nDry run — {len(servers)} servers × {len(scanners)} scanners = {len(servers) * len(scanners)} scans")
        return

    print("-" * 50)

    total_findings = 0
    total_scans = 0
    errors = 0

    for i, server in enumerate(servers, 1):
        slug = server["name"].replace("/", "-").replace("@", "").replace(" ", "-").lower()
        server_dir = SCANS_DIR / slug
        server_dir.mkdir(parents=True, exist_ok=True)

        print(f"[{i}/{len(servers)}] {server['name']} ({server['category']})")

        tmpdir = tempfile.mkdtemp(prefix="mcp_scan_")
        try:
            config_path = make_mcp_config(server, tmpdir)
            if not config_path:
                print(f"  SKIP: No install command")
                continue

            for scanner_name in scanners:
                runner = SCANNER_RUNNERS[scanner_name]
                start = time.time()

                result = runner(server, config_path, server_dir)
                elapsed = time.time() - start

                output_path = server_dir / f"{scanner_name.replace('-', '_')}.json"
                with open(output_path, "w") as f:
                    json.dump(result, f, indent=2)

                n_findings = len(result.get("findings", []))
                total_findings += n_findings
                total_scans += 1

                error = result.get("error", "")
                if error:
                    errors += 1
                    print(f"  [{scanner_name}] {n_findings} findings, {elapsed:.1f}s — ERROR: {error[:80]}")
                else:
                    print(f"  [{scanner_name}] {n_findings} findings, {elapsed:.1f}s")

        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    print("-" * 50)
    print(f"Scans: {total_scans} | Findings: {total_findings} | Errors: {errors}")
    print(f"Results: {SCANS_DIR}")


if __name__ == "__main__":
    main()
