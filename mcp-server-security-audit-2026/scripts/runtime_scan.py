#!/usr/bin/env python3
"""
Runtime MCP Server Scanner
MCP Server Security Audit 2026

Connects to each MCP server, lists its tools, and analyzes tool descriptions
for prompt injection patterns, excessive permissions, and data exfiltration risks.

This is the real security analysis — not static config checks.

Usage:
    python3 runtime_scan.py                    # Scan all servers
    python3 runtime_scan.py --limit 5          # Test with 5 servers
    python3 runtime_scan.py --server context7  # Scan one server
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
STUDY_DIR = SCRIPT_DIR.parent
SELECTED = STUDY_DIR / "inventory" / "selected-100.json"
SCANS_DIR = STUDY_DIR / "scans"

TIMEOUT_CONNECT = 30
TIMEOUT_LIST = 15

# Prompt injection patterns in tool descriptions
INJECTION_PATTERNS = [
    (r"(?i)ignore\s+(previous|all|prior|above)\s+(instructions?|prompts?|rules?)", "prompt-injection-ignore", "HIGH", "Tool description contains instruction override pattern"),
    (r"(?i)you\s+(must|should|need\s+to|have\s+to)\s+(first|always|before)", "prompt-injection-directive", "HIGH", "Tool description contains coercive directive to the LLM"),
    (r"(?i)before\s+using\s+this\s+tool.*(?:call|execute|run|invoke)", "cross-tool-manipulation", "CRITICAL", "Tool description instructs LLM to invoke other tools first"),
    (r"(?i)(?:send|post|upload|transmit|forward|exfiltrate).*(?:to|via)\s+https?://", "data-exfiltration-url", "CRITICAL", "Tool description contains URL-based data exfiltration instruction"),
    (r"(?i)(?:send|forward|copy|move).*(?:data|result|output|response|content).*(?:to|via)\s+\S+", "data-exfiltration-generic", "HIGH", "Tool description instructs data movement to external destination"),
    (r"(?i)you\s+are\s+(?:now|a|an)\s+", "role-hijack", "HIGH", "Tool description attempts to reassign the LLM's role"),
    (r"(?i)(?:bypass|disable|turn\s+off|skip)\s+(?:security|safety|filter|check|validation|auth)", "security-bypass", "CRITICAL", "Tool description instructs bypassing security controls"),
    (r"(?i)do\s+not\s+(?:tell|inform|notify|alert|warn)\s+(?:the\s+)?user", "stealth-instruction", "CRITICAL", "Tool description instructs hiding actions from user"),
    (r"(?i)(?:system|admin|root|sudo)\s+(?:access|privilege|permission|role)", "privilege-escalation", "HIGH", "Tool description references elevated privileges"),
    (r"(?i)(?:password|secret|token|api.?key|credential|private.?key)\s*[:=]", "hardcoded-secret", "CRITICAL", "Tool description contains hardcoded secrets"),
    (r"(?:(?:[a-zA-Z0-9+/]{40,}={0,2}))", "base64-payload", "MEDIUM", "Tool description contains potential Base64-encoded payload"),
    (r"(?i)\\u[0-9a-f]{4}|&#x?[0-9a-f]+;", "encoded-content", "MEDIUM", "Tool description contains Unicode/HTML encoded content"),
]

# Excessive permission patterns in tool schemas
PERMISSION_PATTERNS = [
    (r"(?i)(?:execute|run|eval)\s+(?:any|arbitrary|custom)\s+(?:code|command|script|sql|query)", "arbitrary-execution", "CRITICAL", "Tool allows arbitrary code/command execution"),
    (r"(?i)(?:read|write|access|delete)\s+(?:any|all|every)\s+(?:file|directory|path|folder)", "unrestricted-fs", "HIGH", "Tool has unrestricted filesystem access"),
    (r"(?i)(?:no|without)\s+(?:restriction|limit|validation|sanitization|check)", "no-validation", "HIGH", "Tool explicitly operates without validation"),
    (r"(?i)(?:root|admin|superuser|sudo)\s+(?:access|privilege|mode)", "elevated-privilege", "HIGH", "Tool operates with elevated privileges"),
]

# Schema-level checks
def check_schema_risks(tool_schema):
    findings = []
    input_schema = tool_schema.get("inputSchema", {})
    properties = input_schema.get("properties", {})

    for prop_name, prop_def in properties.items():
        prop_type = prop_def.get("type", "")
        prop_desc = prop_def.get("description", "")

        if prop_name in ("command", "cmd", "exec", "code", "script", "query", "sql") and prop_type == "string":
            findings.append({
                "type": "dangerous-input-parameter",
                "severity": "HIGH",
                "description": f"Parameter '{prop_name}' accepts arbitrary string input for execution",
                "parameter": prop_name,
            })

        if prop_name in ("path", "file", "filepath", "directory", "dir") and prop_type == "string":
            if not prop_def.get("enum") and not prop_def.get("pattern"):
                findings.append({
                    "type": "unvalidated-path-parameter",
                    "severity": "MEDIUM",
                    "description": f"Parameter '{prop_name}' accepts arbitrary file paths without validation",
                    "parameter": prop_name,
                })

        if prop_name in ("url", "endpoint", "uri", "webhook") and prop_type == "string":
            findings.append({
                "type": "url-parameter",
                "severity": "MEDIUM",
                "description": f"Parameter '{prop_name}' accepts arbitrary URLs — potential SSRF vector",
                "parameter": prop_name,
            })

    return findings


def analyze_tool(tool_def):
    findings = []
    name = tool_def.get("name", "")
    description = tool_def.get("description", "")
    full_text = f"{name} {description}"

    for pattern, finding_type, severity, msg in INJECTION_PATTERNS:
        matches = re.findall(pattern, full_text)
        if matches:
            findings.append({
                "type": finding_type,
                "severity": severity,
                "description": msg,
                "match": str(matches[0])[:100] if matches else "",
                "tool_name": name,
                "context": "tool-description",
            })

    for pattern, finding_type, severity, msg in PERMISSION_PATTERNS:
        matches = re.findall(pattern, full_text)
        if matches:
            findings.append({
                "type": finding_type,
                "severity": severity,
                "description": msg,
                "match": str(matches[0])[:100] if matches else "",
                "tool_name": name,
                "context": "tool-description",
            })

    schema_findings = check_schema_risks(tool_def)
    for sf in schema_findings:
        sf["tool_name"] = name
        sf["context"] = "input-schema"
    findings.extend(schema_findings)

    return findings


def connect_and_list_tools(server):
    npm_pkg = server.get("npm_package", "")
    install_cmd = server.get("install_command", "")

    if not npm_pkg and not install_cmd:
        return None, "No install command"

    if npm_pkg:
        command = "npx"
        args = ["-y", npm_pkg]
    else:
        parts = install_cmd.split()
        command = parts[0]
        args = parts[1:]

    # Use MCP Python SDK to connect directly via stdio
    script = f'''
import asyncio, json, sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    params = StdioServerParameters(command="{command}", args={json.dumps(args)})
    try:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.list_tools()
                tools = []
                for t in result.tools:
                    tools.append({{
                        "name": t.name,
                        "description": t.description or "",
                        "inputSchema": t.inputSchema if hasattr(t, "inputSchema") else {{}},
                    }})
                print(json.dumps(tools))
    except Exception as e:
        print(json.dumps({{"error": str(e)}}), file=sys.stderr)
        sys.exit(1)

asyncio.run(main())
'''

    venv_python = str(STUDY_DIR / "venv312" / "bin" / "python3")
    try:
        result = subprocess.run(
            [venv_python, "-c", script],
            capture_output=True, text=True, timeout=TIMEOUT_CONNECT,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )

        if result.returncode != 0:
            err = result.stderr.strip()
            if "error" in err.lower():
                try:
                    err_data = json.loads(err)
                    return None, err_data.get("error", err[:200])
                except json.JSONDecodeError:
                    pass
            return None, err[:200] if err else "Unknown error"

        stdout = result.stdout.strip()
        if not stdout:
            return None, "Empty response"

        tools = json.loads(stdout)
        if isinstance(tools, dict) and "error" in tools:
            return None, tools["error"]

        return tools, None

    except subprocess.TimeoutExpired:
        return None, f"Connection timeout ({TIMEOUT_CONNECT}s)"
    except json.JSONDecodeError as e:
        return None, f"JSON parse error: {e}"


def main():
    parser = argparse.ArgumentParser(description="Runtime MCP server security scanner.")
    parser.add_argument("--server", type=str, help="Scan one server by name")
    parser.add_argument("--limit", type=int, default=0, help="Limit servers to scan")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("MCP Runtime Security Scanner")
    print("=" * 50)

    with open(SELECTED) as f:
        servers = json.load(f)

    if args.server:
        servers = [s for s in servers if args.server in s["name"]]
    if args.limit > 0:
        servers = servers[:args.limit]

    scannable = [s for s in servers if s.get("npm_package") or s.get("install_command")]
    print(f"Total: {len(servers)}, Scannable: {len(scannable)}")

    if args.dry_run:
        for s in scannable:
            print(f"  {s['name']} ({s['category']})")
        return

    print("-" * 50)

    all_results = []
    total_tools = 0
    total_findings = 0
    servers_with_findings = 0
    connection_errors = 0

    for i, server in enumerate(scannable, 1):
        slug = server["name"].replace("/", "-").replace("@", "").replace(" ", "-").lower()
        print(f"[{i}/{len(scannable)}] {server['name']}", end="", flush=True)

        start = time.time()
        tools, error = connect_and_list_tools(server)
        elapsed = time.time() - start

        if error:
            print(f" — ERROR: {error[:60]} ({elapsed:.1f}s)")
            connection_errors += 1
            all_results.append({
                "server": server["name"],
                "category": server.get("category", "unknown"),
                "tools_count": 0,
                "findings": [],
                "error": error,
            })
            continue

        if not tools:
            print(f" — 0 tools ({elapsed:.1f}s)")
            all_results.append({
                "server": server["name"],
                "category": server.get("category", "unknown"),
                "tools_count": 0,
                "findings": [],
            })
            continue

        server_findings = []
        for tool in tools:
            findings = analyze_tool(tool)
            server_findings.extend(findings)

        total_tools += len(tools)
        total_findings += len(server_findings)
        if server_findings:
            servers_with_findings += 1

        print(f" — {len(tools)} tools, {len(server_findings)} findings ({elapsed:.1f}s)")

        result = {
            "server": server["name"],
            "category": server.get("category", "unknown"),
            "tools_count": len(tools),
            "tools": [{"name": t.get("name", ""), "description": t.get("description", "")[:500]} for t in tools],
            "findings": server_findings,
        }
        all_results.append(result)

        # Save per-server
        server_dir = SCANS_DIR / slug
        server_dir.mkdir(parents=True, exist_ok=True)
        with open(server_dir / "runtime_scan.json", "w") as f:
            json.dump(result, f, indent=2)

    # Save combined results
    combined = {
        "scan_date": time.strftime("%Y-%m-%d"),
        "total_servers": len(scannable),
        "servers_connected": len(scannable) - connection_errors,
        "connection_errors": connection_errors,
        "total_tools": total_tools,
        "total_findings": total_findings,
        "servers_with_findings": servers_with_findings,
        "results": all_results,
    }

    output_path = STUDY_DIR / "data" / "runtime_scan_results.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(combined, f, indent=2)

    print("-" * 50)
    print(f"Servers scanned: {len(scannable) - connection_errors}/{len(scannable)}")
    print(f"Connection errors: {connection_errors}")
    print(f"Total tools discovered: {total_tools}")
    print(f"Total findings: {total_findings}")
    print(f"Servers with findings: {servers_with_findings} ({servers_with_findings/(len(scannable)-connection_errors)*100:.1f}%)" if (len(scannable) - connection_errors) > 0 else "")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()
