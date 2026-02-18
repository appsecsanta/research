#!/usr/bin/env python3
"""
Aggregation Script
AI-Generated Code Security Study 2026

Reads the validated validation.csv (filtering to TP findings only), reads
prompt files and config.json, then produces a Hugo data file at
hugo-site/data/ai_code_study_2026.json.

Usage:
    python3 analysis/aggregate.py                     # Default paths
    python3 analysis/aggregate.py --csv validation.csv --output ../../data/ai_code_study_2026.json
    python3 analysis/aggregate.py --scan-date 2026-03-01
"""

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
STUDY_DIR = SCRIPT_DIR.parent
HUGO_SITE_DIR = STUDY_DIR.parent
DEFAULT_CSV = SCRIPT_DIR / "validation.csv"
DEFAULT_OUTPUT = HUGO_SITE_DIR / "data" / "ai_code_study_2026.json"
CONFIG_PATH = STUDY_DIR / "config.json"
PROMPTS_DIR = STUDY_DIR / "prompts"

# OWASP Top 10 (2021) category names
OWASP_NAMES = {
    "A01": "Broken Access Control",
    "A02": "Cryptographic Failures",
    "A03": "Injection",
    "A04": "Insecure Design",
    "A05": "Security Misconfiguration",
    "A06": "Vulnerable & Outdated Components",
    "A07": "Identification & Authentication Failures",
    "A08": "Software & Data Integrity Failures",
    "A09": "Security Logging & Monitoring Failures",
    "A10": "Server-Side Request Forgery",
}

# Common CWE names (top 30+)
CWE_NAMES = {
    "CWE-20": "Improper Input Validation",
    "CWE-22": "Path Traversal",
    "CWE-77": "Command Injection",
    "CWE-78": "OS Command Injection",
    "CWE-79": "Cross-site Scripting (XSS)",
    "CWE-89": "SQL Injection",
    "CWE-90": "LDAP Injection",
    "CWE-94": "Code Injection",
    "CWE-116": "Improper Encoding or Escaping of Output",
    "CWE-200": "Exposure of Sensitive Information",
    "CWE-209": "Information Exposure Through Error Message",
    "CWE-250": "Execution with Unnecessary Privileges",
    "CWE-259": "Use of Hard-coded Password",
    "CWE-269": "Improper Privilege Management",
    "CWE-276": "Incorrect Default Permissions",
    "CWE-287": "Improper Authentication",
    "CWE-295": "Improper Certificate Validation",
    "CWE-306": "Missing Authentication for Critical Function",
    "CWE-307": "Improper Restriction of Excessive Authentication Attempts",
    "CWE-312": "Cleartext Storage of Sensitive Information",
    "CWE-319": "Cleartext Transmission of Sensitive Information",
    "CWE-326": "Inadequate Encryption Strength",
    "CWE-327": "Use of a Broken or Risky Cryptographic Algorithm",
    "CWE-328": "Use of Weak Hash",
    "CWE-330": "Use of Insufficiently Random Values",
    "CWE-338": "Use of Cryptographically Weak PRNG",
    "CWE-352": "Cross-Site Request Forgery (CSRF)",
    "CWE-362": "Race Condition",
    "CWE-384": "Session Fixation",
    "CWE-400": "Uncontrolled Resource Consumption",
    "CWE-434": "Unrestricted Upload of File with Dangerous Type",
    "CWE-476": "NULL Pointer Dereference",
    "CWE-502": "Deserialization of Untrusted Data",
    "CWE-522": "Insufficiently Protected Credentials",
    "CWE-601": "URL Redirection to Untrusted Site",
    "CWE-611": "Improper Restriction of XML External Entity Reference (XXE)",
    "CWE-614": "Sensitive Cookie Without Secure Flag",
    "CWE-639": "Authorization Bypass Through User-Controlled Key (IDOR)",
    "CWE-693": "Protection Mechanism Failure",
    "CWE-703": "Improper Check or Handling of Exceptional Conditions",
    "CWE-732": "Incorrect Permission Assignment for Critical Resource",
    "CWE-749": "Exposed Dangerous Method or Function",
    "CWE-757": "Selection of Less-Secure Algorithm During Negotiation",
    "CWE-798": "Use of Hard-coded Credentials",
    "CWE-862": "Missing Authorization",
    "CWE-863": "Incorrect Authorization",
    "CWE-918": "Server-Side Request Forgery (SSRF)",
    "CWE-943": "Improper Neutralization of Special Elements in Data Query Logic (NoSQL Injection)",
    "CWE-1004": "Sensitive Cookie Without HttpOnly Flag",
    "CWE-1333": "Inefficient Regular Expression Complexity (ReDoS)",
}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_config():
    """Load model definitions from config.json."""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_models():
    """Return a dict mapping model_id -> display_name from config."""
    config = load_config()
    return {m["id"]: m["name"] for m in config.get("models", [])}


def count_prompts():
    """
    Count total prompts from prompts/{language}/*.json files.

    Returns (total_prompts, prompts_by_language).
    """
    total = 0
    by_language = {}

    if not PROMPTS_DIR.is_dir():
        return 0, {}

    for lang_dir in sorted(PROMPTS_DIR.iterdir()):
        if not lang_dir.is_dir() or lang_dir.name.startswith("."):
            continue
        lang = lang_dir.name
        lang_count = 0
        for prompt_file in lang_dir.glob("*.json"):
            try:
                with open(prompt_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                lang_count += len(data.get("prompts", []))
            except (json.JSONDecodeError, OSError):
                continue
        by_language[lang] = lang_count
        total += lang_count

    return total, by_language


def load_validation_csv(csv_path):
    """
    Load validation.csv and return all rows as dicts.

    Each row has: finding_id, model, file, line, cwe, owasp, severity,
    tools, validated, notes.
    """
    rows = []
    if not csv_path.exists():
        return rows

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    return rows


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------


def extract_language_from_file(filepath):
    """Infer language from file path or extension."""
    p = Path(filepath)
    parts = p.parts
    # Path structure: {language}/{owasp_id}/{filename}
    if len(parts) >= 1 and parts[0] in ("python", "javascript"):
        return parts[0]
    ext = p.suffix.lower()
    ext_map = {".py": "python", ".js": "javascript"}
    return ext_map.get(ext, "unknown")


def parse_tools(tools_str):
    """Parse comma-separated tools string into a list."""
    if not tools_str:
        return []
    return [t.strip() for t in tools_str.split(",") if t.strip()]


def get_cwe_name(cwe_id):
    """Look up human-readable CWE name, falling back to the ID itself."""
    return CWE_NAMES.get(cwe_id, cwe_id)


# ---------------------------------------------------------------------------
# Main aggregation
# ---------------------------------------------------------------------------


def aggregate(rows, scan_date="2026-02-XX"):
    """
    Build the full aggregation data structure from validated CSV rows.

    Only TP (True Positive) findings are counted in vulnerability metrics.
    FP findings are counted separately in metadata.
    """
    model_names = load_models()
    total_prompts, prompts_by_language = count_prompts()
    model_ids = list(model_names.keys())

    # Separate TP and FP rows
    tp_rows = [r for r in rows if r.get("validated", "").strip().upper() == "TP"]
    fp_rows = [r for r in rows if r.get("validated", "").strip().upper() == "FP"]

    # Collect all tools seen across all rows (TP and FP)
    all_tools_seen = set()
    for r in rows:
        for tool in parse_tools(r.get("tools", "")):
            all_tools_seen.add(tool)

    # total_code_samples = total_prompts * number of models
    total_models = len(model_ids)
    total_code_samples = total_prompts * total_models

    # -----------------------------------------------------------------------
    # by_model
    # -----------------------------------------------------------------------
    by_model = {}

    for model_id in model_ids:
        model_tp = [r for r in tp_rows if r.get("model") == model_id]

        # Vulnerable samples = unique files with at least one TP finding
        vulnerable_files = set(r.get("file", "") for r in model_tp if r.get("file"))
        vulnerable_count = len(vulnerable_files)

        # Total samples for this model = total_prompts (all prompts sent to all models)
        model_total_samples = total_prompts

        vuln_rate = round(
            (vulnerable_count / model_total_samples * 100) if model_total_samples > 0 else 0.0,
            1,
        )

        # OWASP breakdown
        model_owasp = Counter()
        for r in model_tp:
            owasp = r.get("owasp", "").strip()
            if owasp:
                model_owasp[owasp] += 1

        # Language breakdown
        model_by_lang = {}
        lang_files = defaultdict(set)     # lang -> set of all files
        lang_vuln_files = defaultdict(set) # lang -> set of vulnerable files
        for r in model_tp:
            lang = extract_language_from_file(r.get("file", ""))
            if lang == "unknown":
                continue
            lang_vuln_files[lang].add(r.get("file", ""))

        # Total files per language = prompts in that language
        for lang, lang_prompt_count in prompts_by_language.items():
            vuln_in_lang = len(lang_vuln_files.get(lang, set()))
            lang_total = lang_prompt_count  # each prompt = one code sample per model
            lang_vuln_rate = round(
                (vuln_in_lang / lang_total * 100) if lang_total > 0 else 0.0,
                1,
            )
            model_by_lang[lang] = {
                "vuln_rate": lang_vuln_rate,
                "total": lang_total,
                "vulnerable": vuln_in_lang,
            }

        # Severity breakdown
        model_severity = Counter()
        for r in model_tp:
            sev = r.get("severity", "").strip().upper()
            if sev:
                model_severity[sev] += 1

        by_model[model_id] = {
            "name": model_names.get(model_id, model_id),
            "total_samples": model_total_samples,
            "vulnerable_samples": vulnerable_count,
            "vulnerability_rate": vuln_rate,
            "total_findings": len(model_tp),
            "by_owasp": dict(sorted(model_owasp.items())),
            "by_language": dict(sorted(model_by_lang.items())),
            "by_severity": dict(sorted(model_severity.items())),
        }

    # -----------------------------------------------------------------------
    # by_owasp (across all models)
    # -----------------------------------------------------------------------
    by_owasp = {}
    for owasp_id, owasp_name in sorted(OWASP_NAMES.items()):
        owasp_tp = [r for r in tp_rows if r.get("owasp", "").strip() == owasp_id]
        owasp_by_model = Counter()
        for r in owasp_tp:
            owasp_by_model[r.get("model", "")] += 1
        by_owasp[owasp_id] = {
            "name": owasp_name,
            "total_findings": len(owasp_tp),
            "by_model": dict(sorted(owasp_by_model.items())),
        }

    # -----------------------------------------------------------------------
    # by_language (across all models)
    # -----------------------------------------------------------------------
    by_language = {}
    for lang, lang_prompt_count in sorted(prompts_by_language.items()):
        lang_tp = [
            r for r in tp_rows
            if extract_language_from_file(r.get("file", "")) == lang
        ]

        # Overall vuln rate for this language across all models
        lang_vuln_files_all = set(r.get("file", "") for r in lang_tp if r.get("file"))
        # Total samples for this language = prompts_in_lang * total_models
        lang_total_all = lang_prompt_count * total_models
        lang_vuln_rate_all = round(
            (len(lang_vuln_files_all) / lang_total_all * 100) if lang_total_all > 0 else 0.0,
            1,
        )

        lang_by_model = {}
        for model_id in model_ids:
            model_lang_tp = [
                r for r in lang_tp if r.get("model") == model_id
            ]
            model_lang_vuln_files = set(
                r.get("file", "") for r in model_lang_tp if r.get("file")
            )
            model_lang_total = lang_prompt_count
            model_lang_rate = round(
                (len(model_lang_vuln_files) / model_lang_total * 100)
                if model_lang_total > 0 else 0.0,
                1,
            )
            if model_lang_tp:  # only include models that have findings in this language
                lang_by_model[model_id] = {"vuln_rate": model_lang_rate}

        by_language[lang] = {
            "vuln_rate": lang_vuln_rate_all,
            "by_model": dict(sorted(lang_by_model.items())),
        }

    # -----------------------------------------------------------------------
    # tool_agreement
    # -----------------------------------------------------------------------
    single_tool = 0
    two_tools = 0
    three_plus = 0
    for r in tp_rows:
        tools = parse_tools(r.get("tools", ""))
        n = len(tools)
        if n >= 3:
            three_plus += 1
        elif n == 2:
            two_tools += 1
        else:
            single_tool += 1

    tool_agreement = {
        "single_tool_only": single_tool,
        "two_tools": two_tools,
        "three_or_more": three_plus,
    }

    # -----------------------------------------------------------------------
    # top_cwes
    # -----------------------------------------------------------------------
    cwe_counter = Counter()
    for r in tp_rows:
        cwe = r.get("cwe", "").strip()
        if cwe:
            cwe_counter[cwe] += 1

    top_cwes = [
        {"cwe": cwe, "name": get_cwe_name(cwe), "count": count}
        for cwe, count in cwe_counter.most_common(20)
    ]

    # -----------------------------------------------------------------------
    # Assemble final structure
    # -----------------------------------------------------------------------
    result = {
        "metadata": {
            "total_prompts": total_prompts,
            "total_models": total_models,
            "total_code_samples": total_code_samples,
            "total_findings_raw": len(rows),
            "total_findings_validated_tp": len(tp_rows),
            "total_findings_validated_fp": len(fp_rows),
            "scan_date": scan_date,
            "models": [model_names.get(mid, mid) for mid in model_ids],
            "tools": sorted(all_tools_seen) if all_tools_seen else [],
        },
        "by_model": by_model,
        "by_owasp": by_owasp,
        "by_language": by_language,
        "tool_agreement": tool_agreement,
        "top_cwes": top_cwes,
    }

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Aggregate validated findings into a Hugo data file. "
            "Reads validation.csv (filters to TP findings) and config.json, "
            "then outputs ai_code_study_2026.json for Hugo templates."
        )
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=DEFAULT_CSV,
        help=f"Input validation CSV (default: {DEFAULT_CSV})",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output JSON path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--scan-date",
        type=str,
        default="2026-02-XX",
        help="Date string for metadata.scan_date (default: 2026-02-XX)",
    )
    args = parser.parse_args()

    print("Aggregation Script")
    print("=" * 50)

    # Load validation CSV
    print(f"Input:  {args.csv}")
    rows = load_validation_csv(args.csv)

    if not rows:
        print("No validation data found.")
        print(f"  Looked for: {args.csv}")
        print("  Run validate.py first, then manually review the CSV.")
        print()
        print("Generating empty structure with metadata only...")

    # Count validated rows
    tp_count = sum(1 for r in rows if r.get("validated", "").strip().upper() == "TP")
    fp_count = sum(1 for r in rows if r.get("validated", "").strip().upper() == "FP")
    unreviewed = len(rows) - tp_count - fp_count
    print(f"Total rows: {len(rows)}")
    print(f"  TP: {tp_count} | FP: {fp_count} | Unreviewed: {unreviewed}")

    if unreviewed > 0 and rows:
        print(f"\n  WARNING: {unreviewed} findings not yet validated (TP/FP)")
        print("  These will be excluded from aggregation.")

    # Run aggregation
    result = aggregate(rows, scan_date=args.scan_date)

    # Write output
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\nOutput: {args.output}")
    print()

    # Print summary
    meta = result["metadata"]
    print("Summary:")
    print(f"  Prompts:        {meta['total_prompts']}")
    print(f"  Models:         {meta['total_models']} ({', '.join(meta['models'])})")
    print(f"  Code samples:   {meta['total_code_samples']}")
    print(f"  Findings (raw): {meta['total_findings_raw']}")
    print(f"  Findings (TP):  {meta['total_findings_validated_tp']}")
    print(f"  Findings (FP):  {meta['total_findings_validated_fp']}")

    if result["top_cwes"]:
        print(f"\nTop CWEs:")
        for entry in result["top_cwes"][:5]:
            print(f"  {entry['cwe']}: {entry['name']} ({entry['count']})")

    # Model vulnerability rates
    if any(m["total_findings"] > 0 for m in result["by_model"].values()):
        print(f"\nVulnerability rates by model:")
        for model_id, data in sorted(
            result["by_model"].items(),
            key=lambda x: x[1]["vulnerability_rate"],
            reverse=True,
        ):
            print(
                f"  {data['name']:25s} "
                f"{data['vulnerability_rate']:5.1f}% "
                f"({data['vulnerable_samples']}/{data['total_samples']} samples, "
                f"{data['total_findings']} findings)"
            )


if __name__ == "__main__":
    main()
