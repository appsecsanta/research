#!/usr/bin/env python3
"""
normalize-results.py — Normalize output from 11 security scanning tools
into a unified CSV format for the CandyShop Benchmark.

Usage:
    python3 normalize-results.py results/2026-03-01
    python3 normalize-results.py results/2026-03-01 > results/normalized-all.csv

Unified CSV schema:
    finding_id,tool,target,category,cwe,severity,location,description,raw_id

Supports:
    Container: trivy, grype
    SAST:      bearer, nodejsscan, bandit
    SCA:       npm-audit, pip-audit, dep-check
    DAST:      zap, nuclei
    IaC:       checkov
"""

import csv
import json
import os
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Severity normalization maps
# ---------------------------------------------------------------------------

TRIVY_SEVERITY = {
    "CRITICAL": "CRITICAL",
    "HIGH": "HIGH",
    "MEDIUM": "MEDIUM",
    "LOW": "LOW",
    "UNKNOWN": "INFO",
}

GRYPE_SEVERITY = {
    "Critical": "CRITICAL",
    "High": "HIGH",
    "Medium": "MEDIUM",
    "Low": "LOW",
    "Negligible": "INFO",
}

NODEJSSCAN_SEVERITY = {
    "ERROR": "HIGH",
    "WARNING": "MEDIUM",
    "INFO": "LOW",
}

ZAP_RISK = {
    "3": "HIGH",
    "2": "MEDIUM",
    "1": "LOW",
    "0": "INFO",
}

# Bearer and Bandit already use standard severity strings (case-insensitive).
# Nuclei uses lowercase standard severity strings.
STANDARD_SEVERITY = {
    "critical": "CRITICAL",
    "high": "HIGH",
    "medium": "MEDIUM",
    "low": "LOW",
    "info": "INFO",
    "warning": "MEDIUM",
    "error": "HIGH",
}

# Tool → category mapping
TOOL_CATEGORY = {
    "trivy": "container",
    "grype": "container",
    "bearer": "sast",
    "nodejsscan": "sast",
    "bandit": "sast",
    "npm-audit": "sca",
    "pip-audit": "sca",
    "dep-check": "sca",
    "zap": "dast",
    "nuclei": "dast",
    "checkov": "iac",
}

KNOWN_TARGETS = {
    "juice-shop", "broken-crystals", "altoro-mutual",
    "vulnpy", "dvwa", "webgoat",
}


# ---------------------------------------------------------------------------
# Counters
# ---------------------------------------------------------------------------
class Stats:
    files_processed = 0
    total_findings = 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def warn(msg):
    """Print a warning to stderr."""
    print(f"WARNING: {msg}", file=sys.stderr)


def load_json(filepath):
    """Load a JSON file, returning None on failure."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        warn(f"Malformed JSON in {filepath}: {e}")
        return None
    except Exception as e:
        warn(f"Error reading {filepath}: {e}")
        return None


def load_jsonl(filepath):
    """Load a JSONL file (one JSON object per line). Returns a list of dicts."""
    results = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    results.append(json.loads(line))
                except json.JSONDecodeError as e:
                    warn(f"Malformed JSON at {filepath}:{lineno}: {e}")
    except Exception as e:
        warn(f"Error reading {filepath}: {e}")
    return results


def normalize_severity(raw, mapping=None):
    """Normalize a severity string using the given mapping or standard map."""
    if not raw:
        return "INFO"
    if mapping:
        result = mapping.get(raw) or mapping.get(str(raw))
        if result:
            return result
    # Fallback to standard case-insensitive lookup
    result = STANDARD_SEVERITY.get(raw.lower())
    if result:
        return result
    # If already uppercase and valid, return as-is
    upper = raw.upper()
    if upper in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"):
        return upper
    return "INFO"


def make_finding_id(tool, target, counter):
    """Generate a finding_id like TRIVY-JUICE-SHOP-001."""
    tool_part = tool.upper().replace("-", "")
    target_part = target.upper().replace("-", "-")
    return f"{tool_part}-{target_part}-{counter:03d}"


def sanitize(text):
    """Clean text for CSV output — collapse whitespace, strip newlines."""
    if not text:
        return ""
    return " ".join(str(text).split())


def extract_target_from_path(filepath, results_dir):
    """Try to extract target name from path structure or filename."""
    rel = os.path.relpath(filepath, results_dir)
    parts = Path(rel).parts

    # Flat structure: {target}/tool.json → parts[0] is target
    if len(parts) >= 2 and parts[0] in KNOWN_TARGETS:
        return parts[0]

    # Categorized structure: {phase}/tool-{target}.json
    filename = Path(filepath).stem  # e.g., "trivy-juice-shop"
    for target in sorted(KNOWN_TARGETS, key=len, reverse=True):
        if filename.endswith(f"-{target}"):
            return target

    return None


# ---------------------------------------------------------------------------
# Tool-specific parsers
# Each returns a list of dicts matching the CSV schema fields.
# ---------------------------------------------------------------------------

def parse_trivy(filepath, target):
    data = load_json(filepath)
    if data is None:
        return []
    findings = []
    results = data.get("Results") or []
    for result_block in results:
        vulns = result_block.get("Vulnerabilities") or []
        for v in vulns:
            cwe_list = v.get("CweIDs") or []
            cwe = cwe_list[0] if cwe_list else ""
            pkg = v.get("PkgName", "")
            ver = v.get("InstalledVersion", "")
            location = f"{pkg}@{ver}" if pkg else ""
            findings.append({
                "tool": "trivy",
                "target": target,
                "category": "container",
                "cwe": cwe,
                "severity": normalize_severity(v.get("Severity"), TRIVY_SEVERITY),
                "location": location,
                "description": sanitize(v.get("Title") or v.get("Description", "")),
                "raw_id": v.get("VulnerabilityID", ""),
            })
    return findings


def parse_grype(filepath, target):
    data = load_json(filepath)
    if data is None:
        return []
    findings = []
    matches = data.get("matches") or []
    for m in matches:
        vuln = m.get("vulnerability", {})
        artifact = m.get("artifact", {})
        related = vuln.get("relatedVulnerabilities") or []
        # Try to get CWE from related vulnerabilities
        cwe = ""
        for rel in related:
            cwes = rel.get("cwes") or []
            if cwes:
                cwe_id = cwes[0].get("cweId") if isinstance(cwes[0], dict) else cwes[0]
                cwe = f"CWE-{cwe_id}" if cwe_id and not str(cwe_id).startswith("CWE") else str(cwe_id)
                break
        pkg = artifact.get("name", "")
        ver = artifact.get("version", "")
        location = f"{pkg}@{ver}" if pkg else ""
        findings.append({
            "tool": "grype",
            "target": target,
            "category": "container",
            "cwe": cwe,
            "severity": normalize_severity(vuln.get("severity"), GRYPE_SEVERITY),
            "location": location,
            "description": sanitize(vuln.get("description", "")),
            "raw_id": vuln.get("id", ""),
        })
    return findings


def parse_bearer(filepath, target):
    data = load_json(filepath)
    if data is None:
        return []
    findings_list = []

    # Bearer output can have findings at top-level or nested
    raw_findings = data.get("findings") or []
    if not raw_findings and isinstance(data, dict):
        # Some Bearer versions wrap differently
        for key in data:
            if isinstance(data[key], list):
                for item in data[key]:
                    if isinstance(item, dict) and "filename" in item:
                        raw_findings.append(item)

    for f in raw_findings:
        cwe_ids = f.get("cwe_ids") or []
        cwe = cwe_ids[0] if cwe_ids else ""
        # Ensure CWE format
        if cwe and not str(cwe).startswith("CWE"):
            cwe = f"CWE-{cwe}"
        filename = f.get("filename", "")
        line = f.get("line_number", "")
        location = f"{filename}:{line}" if filename and line else filename
        findings_list.append({
            "tool": "bearer",
            "target": target,
            "category": "sast",
            "cwe": cwe,
            "severity": normalize_severity(f.get("severity", "")),
            "location": location,
            "description": sanitize(f.get("description", "") or f.get("title", "")),
            "raw_id": f.get("rule_id", ""),
        })
    return findings_list


def parse_nodejsscan(filepath, target):
    data = load_json(filepath)
    if data is None:
        return []
    findings = []
    sec_issues = data.get("sec_issues") or {}
    # Also check top-level keys for alternative structures
    if not sec_issues and "nodejs" in data:
        sec_issues = data.get("nodejs", {})

    for category_name, issues in sec_issues.items():
        if not isinstance(issues, list):
            continue
        for issue in issues:
            filename = issue.get("filename", "")
            line = issue.get("line", "")
            location = f"{filename}:{line}" if filename and line else filename
            findings.append({
                "tool": "nodejsscan",
                "target": target,
                "category": "sast",
                "cwe": "",  # njsscan doesn't provide CWE IDs typically
                "severity": normalize_severity(issue.get("severity", ""), NODEJSSCAN_SEVERITY),
                "location": location,
                "description": sanitize(issue.get("description", "") or issue.get("title", "")),
                "raw_id": issue.get("title", category_name),
            })
    return findings


def parse_bandit(filepath, target):
    data = load_json(filepath)
    if data is None:
        return []
    findings = []
    results = data.get("results") or []
    for r in results:
        cwe_info = r.get("issue_cwe", {})
        cwe_id = cwe_info.get("id") if isinstance(cwe_info, dict) else ""
        cwe = f"CWE-{cwe_id}" if cwe_id else ""
        filename = r.get("filename", "")
        line = r.get("line_number", "")
        location = f"{filename}:{line}" if filename and line else filename
        findings.append({
            "tool": "bandit",
            "target": target,
            "category": "sast",
            "cwe": cwe,
            "severity": normalize_severity(r.get("severity", "")),
            "location": location,
            "description": sanitize(r.get("issue_text", "")),
            "raw_id": r.get("test_id", ""),
        })
    return findings


def parse_zap(filepath, target):
    data = load_json(filepath)
    if data is None:
        return []
    findings = []

    # ZAP can have {"site": [{"alerts": [...]}]} or flat {"alerts": [...]}
    alerts = []
    if "site" in data:
        sites = data["site"]
        if isinstance(sites, list):
            for site in sites:
                alerts.extend(site.get("alerts") or [])
        elif isinstance(sites, dict):
            alerts.extend(sites.get("alerts") or [])
    elif "alerts" in data:
        alerts = data["alerts"] or []

    for alert in alerts:
        cweid = alert.get("cweid", "")
        cwe = f"CWE-{cweid}" if cweid and str(cweid) != "0" and str(cweid) != "-1" else ""
        risk = str(alert.get("riskcode", alert.get("risk", "")))
        # Get first instance URI as location
        instances = alert.get("instances") or []
        if instances and isinstance(instances, list):
            location = instances[0].get("uri", "")
        else:
            location = alert.get("url", "")
        findings.append({
            "tool": "zap",
            "target": target,
            "category": "dast",
            "cwe": cwe,
            "severity": normalize_severity(risk, ZAP_RISK),
            "location": sanitize(location),
            "description": sanitize(alert.get("name", "") or alert.get("alert", "")),
            "raw_id": str(alert.get("pluginid", alert.get("alertRef", ""))),
        })
    return findings


def parse_nuclei(filepath, target):
    """Nuclei outputs JSON array or JSONL — handle both formats."""
    # Try JSON array first (nuclei -json-export produces an array)
    data = load_json(filepath)
    if isinstance(data, list):
        records = data
    else:
        # Fallback to JSONL (one JSON object per line)
        records = load_jsonl(filepath)
    findings = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        info = rec.get("info", {})
        classification = info.get("classification", {}) or {}
        cwe_ids = classification.get("cwe-id") or []
        cwe = cwe_ids[0] if cwe_ids else ""
        if cwe and not str(cwe).startswith("CWE"):
            cwe = f"CWE-{cwe}"
        findings.append({
            "tool": "nuclei",
            "target": target,
            "category": "dast",
            "cwe": cwe,
            "severity": normalize_severity(info.get("severity", "")),
            "location": sanitize(rec.get("matched-at", rec.get("host", ""))),
            "description": sanitize(info.get("name", "")),
            "raw_id": rec.get("template-id", ""),
        })
    return findings


def parse_npm_audit(filepath, target):
    data = load_json(filepath)
    if data is None:
        return []
    findings = []
    vulns = data.get("vulnerabilities") or {}
    for pkg_name, vuln_info in vulns.items():
        if not isinstance(vuln_info, dict):
            continue
        severity = vuln_info.get("severity", "")
        via = vuln_info.get("via") or []
        # "via" can be a list of dicts or strings (when advisory comes from
        # another package). We only want the dict entries.
        description = ""
        cwe = ""
        raw_id = ""
        for v in via:
            if isinstance(v, dict):
                description = description or sanitize(v.get("title", ""))
                cwe_list = v.get("cwe") or []
                if cwe_list and not cwe:
                    cwe = cwe_list[0] if isinstance(cwe_list[0], str) else ""
                raw_url = v.get("url", "")
                if not raw_id and raw_url:
                    # Extract GHSA or advisory ID from URL
                    raw_id = raw_url.rsplit("/", 1)[-1] if "/" in raw_url else raw_url
                if not raw_id:
                    raw_id = str(v.get("source", ""))
        # If no dict entries in via, use the string references
        if not description and via:
            str_refs = [v for v in via if isinstance(v, str)]
            if str_refs:
                description = f"Dependency of: {', '.join(str_refs)}"

        location = pkg_name
        findings.append({
            "tool": "npm-audit",
            "target": target,
            "category": "sca",
            "cwe": cwe,
            "severity": normalize_severity(severity),
            "location": location,
            "description": description,
            "raw_id": raw_id,
        })
    return findings


def parse_pip_audit(filepath, target):
    data = load_json(filepath)
    if data is None:
        return []
    findings = []
    deps = data.get("dependencies") or []
    for dep in deps:
        pkg = dep.get("name", "")
        ver = dep.get("version", "")
        vulns = dep.get("vulns") or []
        for v in vulns:
            vuln_id = v.get("id", "")
            # pip-audit doesn't natively provide severity; default to MEDIUM
            # Some entries have fix_versions which hints at severity but
            # no reliable mapping exists.
            location = f"{pkg}@{ver}" if pkg else ""
            findings.append({
                "tool": "pip-audit",
                "target": target,
                "category": "sca",
                "cwe": "",
                "severity": "MEDIUM",
                "location": location,
                "description": sanitize(v.get("description", "")),
                "raw_id": vuln_id,
            })
    return findings


def parse_dep_check(filepath, target):
    data = load_json(filepath)
    if data is None:
        return []
    findings = []
    deps = data.get("dependencies") or []
    for dep in deps:
        dep_vulns = dep.get("vulnerabilities") or []
        filename = dep.get("fileName", "")
        for v in dep_vulns:
            cwes = v.get("cwes") or []
            cwe = ""
            if cwes:
                first_cwe = cwes[0]
                if isinstance(first_cwe, str):
                    cwe = first_cwe if first_cwe.startswith("CWE") else f"CWE-{first_cwe}"
                elif isinstance(first_cwe, dict):
                    cwe = first_cwe.get("cwe", "")
                elif isinstance(first_cwe, int):
                    cwe = f"CWE-{first_cwe}"
            findings.append({
                "tool": "dep-check",
                "target": target,
                "category": "sca",
                "cwe": cwe,
                "severity": normalize_severity(v.get("severity", "")),
                "location": filename,
                "description": sanitize(v.get("description", "")),
                "raw_id": v.get("name", ""),
            })
    return findings


def parse_checkov(filepath, results_dir):
    """Checkov is special: single file covering all targets.
    Target is extracted from file_path in each check."""
    data = load_json(filepath)
    if data is None:
        return []
    findings = []

    # Checkov output can be a list of framework results or a single dict
    results_list = []
    if isinstance(data, list):
        results_list = data
    elif isinstance(data, dict):
        results_list = [data]

    for result_block in results_list:
        if not isinstance(result_block, dict):
            continue
        checks = (result_block.get("results", {}) or {}).get("failed_checks") or []
        for check in checks:
            file_path = check.get("file_path", "")
            # Try to extract target from the file path
            # e.g., /targets/vulnpy/Dockerfile → vulnpy
            target = "unknown"
            for t in KNOWN_TARGETS:
                if t in file_path:
                    target = t
                    break

            resource = check.get("resource", "")
            location = f"{file_path}:{resource}" if resource else file_path
            findings.append({
                "tool": "checkov",
                "target": target,
                "category": "iac",
                "cwe": "",
                "severity": "MEDIUM",
                "location": location,
                "description": sanitize(check.get("check_id", "") + ": " + (check.get("guideline", "") or check.get("check_type", ""))),
                "raw_id": check.get("check_id", ""),
            })
    return findings


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

def discover_files(results_dir):
    """Walk the results directory and yield (tool, target, filepath) tuples."""
    results_path = Path(results_dir)
    if not results_path.is_dir():
        print(f"ERROR: Results directory not found: {results_dir}", file=sys.stderr)
        sys.exit(1)

    # Categorized structure: {results_dir}/{phase}/tool-{target}.json
    # Phases: container, sast, sca, dast, iac
    tool_prefixes = {
        "trivy": "trivy",
        "grype": "grype",
        "bearer": "bearer",
        "njsscan": "nodejsscan",
        "bandit": "bandit",
        "zap": "zap",
        "nuclei": "nuclei",
        "npm-audit": "npm-audit",
        "pip-audit": "pip-audit",
    }

    # Walk categorized directories
    for phase_dir in results_path.iterdir():
        if not phase_dir.is_dir():
            continue

        phase_name = phase_dir.name

        # Check if this is a target directory (flat structure)
        if phase_name in KNOWN_TARGETS:
            target = phase_name
            for json_file in phase_dir.glob("*.json"):
                tool_name = json_file.stem  # e.g., "trivy", "grype", "bearer"
                # Map common filename variations
                mapped = tool_prefixes.get(tool_name, tool_name)
                if mapped in TOOL_CATEGORY:
                    yield (mapped, target, str(json_file))
            continue

        # Categorized structure: phase/tool-target.json
        for json_file in phase_dir.glob("*.json"):
            stem = json_file.stem  # e.g., "trivy-juice-shop"

            # Special case: checkov.json (single file, no target in name)
            if stem == "checkov":
                yield ("checkov", "__all__", str(json_file))
                continue

            # Try to match tool-target pattern
            matched = False
            for prefix, tool_name in tool_prefixes.items():
                for target in sorted(KNOWN_TARGETS, key=len, reverse=True):
                    expected = f"{prefix}-{target}"
                    if stem == expected:
                        yield (tool_name, target, str(json_file))
                        matched = True
                        break
                if matched:
                    break

            # Dependency-Check: look inside depcheck-{target}/ directories
            if not matched and json_file.name == "dependency-check-report.json":
                # Parent dir is depcheck-{target}
                parent = json_file.parent.name
                if parent.startswith("depcheck-"):
                    target = parent.replace("depcheck-", "", 1)
                    if target in KNOWN_TARGETS:
                        yield ("dep-check", target, str(json_file))

        # Also check for depcheck-{target} subdirectories
        for sub in phase_dir.iterdir():
            if sub.is_dir() and sub.name.startswith("depcheck-"):
                target = sub.name.replace("depcheck-", "", 1)
                if target in KNOWN_TARGETS:
                    for json_file in sub.glob("*.json"):
                        yield ("dep-check", target, str(json_file))


# ---------------------------------------------------------------------------
# Parser dispatch
# ---------------------------------------------------------------------------

PARSERS = {
    "trivy": parse_trivy,
    "grype": parse_grype,
    "bearer": parse_bearer,
    "nodejsscan": parse_nodejsscan,
    "bandit": parse_bandit,
    "zap": parse_zap,
    "nuclei": parse_nuclei,
    "npm-audit": parse_npm_audit,
    "pip-audit": parse_pip_audit,
    "dep-check": parse_dep_check,
    # checkov handled separately
}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: normalize-results.py <results-dir>", file=sys.stderr)
        print("  e.g.: python3 normalize-results.py results/2026-03-01", file=sys.stderr)
        sys.exit(1)

    results_dir = sys.argv[1]

    # Collect all findings
    all_findings = []
    files_processed = 0

    for tool, target, filepath in discover_files(results_dir):
        files_processed += 1
        print(f"  Parsing: {filepath}", file=sys.stderr)

        if tool == "checkov":
            findings = parse_checkov(filepath, results_dir)
        elif tool == "nuclei":
            findings = parse_nuclei(filepath, target)
        elif tool in PARSERS:
            findings = PARSERS[tool](filepath, target)
        else:
            warn(f"No parser for tool: {tool} ({filepath})")
            continue

        all_findings.extend(findings)

    # Assign finding IDs
    # Group by (tool, target) for sequential numbering
    counters = {}
    for f in all_findings:
        key = (f["tool"], f["target"])
        counters.setdefault(key, 0)
        counters[key] += 1
        f["finding_id"] = make_finding_id(f["tool"], f["target"], counters[key])

    # Write CSV to stdout
    fieldnames = [
        "finding_id", "tool", "target", "category",
        "cwe", "severity", "location", "description", "raw_id",
    ]
    writer = csv.DictWriter(
        sys.stdout,
        fieldnames=fieldnames,
        extrasaction="ignore",
        quoting=csv.QUOTE_MINIMAL,
    )
    writer.writeheader()
    for f in all_findings:
        writer.writerow(f)

    # Summary to stderr
    print(
        f"\nProcessed {files_processed} files, {len(all_findings)} total findings",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
