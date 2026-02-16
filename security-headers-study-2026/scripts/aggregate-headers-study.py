#!/usr/bin/env python3
"""Aggregate security headers scan data for the Headers Adoption Study.

Uses Mozilla Observatory-compatible scoring methodology.
Base score: 100, modifiers per test category.
See: https://github.com/mozilla/http-observatory/blob/main/httpobs/docs/scoring.md

Reads: data/headers_scan_raw.json
Writes: data/headers_study_2026.json
"""

import json
import sys
from collections import Counter
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
INPUT = DATA_DIR / "headers_scan_raw.json"
OUTPUT = DATA_DIR / "headers_study_2026.json"

# --- Mozilla Observatory Grade Chart ---
# Base score: 100, bonuses only if score >= 90 before bonuses
MINIMUM_SCORE_FOR_EXTRA_CREDIT = 90

GRADE_CHART = {
    100: "A+", 95: "A", 90: "A", 85: "A-",
    80: "B+", 75: "B", 70: "B", 65: "B-",
    60: "C+", 55: "C", 50: "C", 45: "C-",
    40: "D+", 35: "D", 30: "D", 25: "D-",
    20: "F", 15: "F", 10: "F", 5: "F", 0: "F",
}

ALL_GRADES = ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "D-", "F"]

SCORED_HEADERS = [
    "content-security-policy",
    "strict-transport-security",
    "x-content-type-options",
    "x-frame-options",
    "permissions-policy",
    "referrer-policy",
    "x-xss-protection",
    "cross-origin-opener-policy",
    "cross-origin-embedder-policy",
    "cross-origin-resource-policy",
]


def score_to_grade(score: int) -> str:
    """Convert numeric score to letter grade using Observatory chart."""
    score = max(score, 0)
    bucket = min(score - score % 5, 100)
    return GRADE_CHART.get(bucket, "F")


def score_csp(headers, csp_parsed):
    """Score Content Security Policy. Observatory range: -25 to +10."""
    csp = headers.get("content-security-policy")
    csp_ro = headers.get("content-security-policy-report-only")

    if not csp and not csp_ro:
        return -25, "csp-not-implemented"

    if not csp_parsed:
        return -25, "csp-header-invalid"

    has_unsafe_inline = csp_parsed.get("uses_unsafe_inline", False)
    has_unsafe_eval = csp_parsed.get("uses_unsafe_eval", False)
    has_default_src = csp_parsed.get("has_default_src", False)

    # Best case: no unsafe, default-src none
    if not has_unsafe_inline and not has_unsafe_eval:
        # Check if default-src is 'none' (we approximate: has default-src and no unsafe)
        if has_default_src:
            return 10, "csp-implemented-with-no-unsafe-default-src-none"
        return 5, "csp-implemented-with-no-unsafe"

    if has_unsafe_eval and not has_unsafe_inline:
        return -10, "csp-implemented-with-unsafe-eval"

    if has_unsafe_inline:
        return -20, "csp-implemented-with-unsafe-inline"

    return 0, "csp-implemented-with-unsafe-inline-in-style-src-only"


def score_hsts(headers, hsts_parsed):
    """Score HSTS. Observatory range: -20 to +5."""
    hsts = headers.get("strict-transport-security")

    if not hsts:
        return -20, "hsts-not-implemented"

    if not hsts_parsed:
        return -20, "hsts-header-invalid"

    max_age = hsts_parsed.get("max_age", 0) or 0
    preload = hsts_parsed.get("preload", False)

    if preload and max_age >= 31536000:
        return 5, "hsts-preloaded"

    if max_age >= 15768000:  # 6 months
        return 0, "hsts-implemented-max-age-at-least-six-months"

    return -10, "hsts-implemented-max-age-less-than-six-months"


def score_x_content_type_options(headers):
    """Score X-Content-Type-Options. Observatory range: -5 to 0."""
    val = headers.get("x-content-type-options")
    if not val:
        return -5, "x-content-type-options-not-implemented"
    if "nosniff" in val.lower():
        return 0, "x-content-type-options-nosniff"
    return -5, "x-content-type-options-header-invalid"


def score_x_frame_options(headers, csp_parsed):
    """Score X-Frame-Options. Observatory range: -20 to +5."""
    xfo = headers.get("x-frame-options")
    csp = headers.get("content-security-policy", "")

    # Check if frame-ancestors is in CSP
    if csp and "frame-ancestors" in csp.lower():
        return 5, "x-frame-options-implemented-via-csp"

    if not xfo:
        return -20, "x-frame-options-not-implemented"

    xfo_lower = xfo.lower().strip()
    if xfo_lower in ("deny", "sameorigin"):
        return 0, "x-frame-options-sameorigin-or-deny"
    if "allow-from" in xfo_lower:
        return 0, "x-frame-options-allow-from-origin"

    return -20, "x-frame-options-header-invalid"


def score_referrer_policy(headers):
    """Score Referrer-Policy. Observatory range: -5 to +5."""
    rp = headers.get("referrer-policy")
    if not rp:
        return 0, "referrer-policy-not-implemented"

    rp_lower = rp.lower().strip()
    private_values = {
        "no-referrer", "same-origin", "strict-origin",
        "strict-origin-when-cross-origin",
    }
    if rp_lower in private_values:
        return 5, "referrer-policy-private"
    if rp_lower == "no-referrer-when-downgrade":
        return 0, "referrer-policy-no-referrer-when-downgrade"
    unsafe_values = {"origin", "origin-when-cross-origin", "unsafe-url"}
    if rp_lower in unsafe_values:
        return -5, "referrer-policy-unsafe"

    return -5, "referrer-policy-header-invalid"


def score_x_xss_protection(headers):
    """Score X-XSS-Protection. Observatory: all 0 except invalid (-5)."""
    val = headers.get("x-xss-protection")
    if not val:
        return 0, "x-xss-protection-not-implemented"
    val = val.strip()
    if val.startswith("1") and "mode=block" in val:
        return 0, "x-xss-protection-enabled-mode-block"
    if val.startswith("1"):
        return 0, "x-xss-protection-enabled"
    if val == "0":
        return 0, "x-xss-protection-disabled"
    return -5, "x-xss-protection-header-invalid"


def score_redirection(result):
    """Score redirection. Observatory range: -20 to 0."""
    url = result.get("url", "")
    final_url = result.get("final_url", "")
    redirected = result.get("redirected", False)

    # If original URL is already HTTPS
    if url.startswith("https://"):
        if not redirected:
            return 0, "redirection-not-needed-no-http"
        if final_url.startswith("https://"):
            return 0, "redirection-to-https"
        return -20, "redirection-not-to-https"

    return 0, "redirection-to-https"  # We always request https://


def compute_observatory_score(result):
    """Compute Observatory-compatible score for a single site.

    Returns (score, grade, test_results).
    Tests we CAN run from HEAD: CSP, HSTS, XCTO, XFO, Referrer-Policy, X-XSS, Redirection
    Tests we CANNOT run (need cookies/HTML): Cookies (0), SRI (0), CORS (0)
    """
    headers = result.get("headers", {})
    csp_parsed = result.get("csp_parsed")
    hsts_parsed = result.get("hsts_parsed")

    tests = {}
    base_score = 100
    bonus_score = 0

    # Run each test
    csp_mod, csp_result = score_csp(headers, csp_parsed)
    tests["csp"] = {"result": csp_result, "modifier": csp_mod}

    hsts_mod, hsts_result = score_hsts(headers, hsts_parsed)
    tests["hsts"] = {"result": hsts_result, "modifier": hsts_mod}

    xcto_mod, xcto_result = score_x_content_type_options(headers)
    tests["x-content-type-options"] = {"result": xcto_result, "modifier": xcto_mod}

    xfo_mod, xfo_result = score_x_frame_options(headers, csp_parsed)
    tests["x-frame-options"] = {"result": xfo_result, "modifier": xfo_mod}

    rp_mod, rp_result = score_referrer_policy(headers)
    tests["referrer-policy"] = {"result": rp_result, "modifier": rp_mod}

    xxss_mod, xxss_result = score_x_xss_protection(headers)
    tests["x-xss-protection"] = {"result": xxss_result, "modifier": xxss_mod}

    redir_mod, redir_result = score_redirection(result)
    tests["redirection"] = {"result": redir_result, "modifier": redir_mod}

    # Tests we cannot run from HEAD requests - assign neutral (0)
    tests["cookies"] = {"result": "cookies-not-found", "modifier": 0, "note": "HEAD request - cannot detect cookies"}
    tests["sri"] = {"result": "sri-not-implemented-response-not-html", "modifier": 0, "note": "HEAD request - no HTML to parse"}
    tests["cors"] = {"result": "cross-origin-resource-sharing-not-implemented", "modifier": 0, "note": "HEAD request - cannot check CORS files"}

    # Separate penalties from bonuses
    for test_name, test_data in tests.items():
        mod = test_data["modifier"]
        if mod > 0:
            bonus_score += mod
        else:
            base_score += mod

    # Bonuses only apply if base score >= 90
    if base_score >= MINIMUM_SCORE_FOR_EXTRA_CREDIT:
        final_score = base_score + bonus_score
    else:
        final_score = base_score

    final_score = max(final_score, 0)
    grade = score_to_grade(final_score)

    return final_score, grade, tests


def main():
    if not INPUT.exists():
        print(f"ERROR: {INPUT} not found. Run scan-headers.js first.")
        sys.exit(1)

    raw = json.load(open(INPUT))
    results = [r for r in raw.get("results", []) if not r.get("error")]

    print(f"Analyzing {len(results)} successful scans with Observatory scoring...")

    if len(results) == 0:
        print("ERROR: No successful scans found.")
        sys.exit(1)

    # Score every site
    scored_results = []
    score_sum = 0
    test_result_counts = Counter()

    for r in results:
        score, grade, tests = compute_observatory_score(r)
        scored_results.append({
            "url": r.get("url"),
            "rank": r.get("rank"),
            "score": score,
            "grade": grade,
            "tests": tests,
        })
        score_sum += score
        for test_name, test_data in tests.items():
            test_result_counts[test_data["result"]] += 1

    # Header adoption rates
    adoption = {}
    for h in SCORED_HEADERS:
        count = sum(1 for r in results if r.get("headers", {}).get(h))
        adoption[h] = {
            "count": count,
            "percentage": round(count / len(results) * 100, 1),
        }

    # CSP report-only (separate)
    csp_report_only_count = sum(
        1 for r in results
        if r.get("headers", {}).get("content-security-policy-report-only")
        and not r.get("headers", {}).get("content-security-policy")
    )
    adoption["content-security-policy-report-only"] = {
        "count": csp_report_only_count,
        "percentage": round(csp_report_only_count / len(results) * 100, 1),
    }

    # Grade distribution
    grades = Counter(sr["grade"] for sr in scored_results)
    grade_distribution = {}
    for g in ALL_GRADES:
        count = grades.get(g, 0)
        grade_distribution[g] = {
            "count": count,
            "percentage": round(count / len(results) * 100, 1),
        }

    # Score statistics
    scores = [sr["score"] for sr in scored_results]
    scores_sorted = sorted(scores)
    avg_score = round(score_sum / len(results), 1)
    median_score = scores_sorted[len(scores_sorted) // 2]

    # CSP analysis (only sites with CSP)
    csp_sites = [r for r in results if r.get("csp_parsed")]
    csp_analysis = {
        "total_with_csp": len(csp_sites),
        "percentage": round(len(csp_sites) / len(results) * 100, 1),
        "uses_unsafe_inline": sum(1 for r in csp_sites if r["csp_parsed"].get("uses_unsafe_inline")),
        "uses_unsafe_eval": sum(1 for r in csp_sites if r["csp_parsed"].get("uses_unsafe_eval")),
        "uses_nonce": sum(1 for r in csp_sites if r["csp_parsed"].get("uses_nonce")),
        "uses_strict_dynamic": sum(1 for r in csp_sites if r["csp_parsed"].get("uses_strict_dynamic")),
        "has_default_src": sum(1 for r in csp_sites if r["csp_parsed"].get("has_default_src")),
        "has_script_src": sum(1 for r in csp_sites if r["csp_parsed"].get("has_script_src")),
        "avg_directive_count": round(
            sum(r["csp_parsed"]["directive_count"] for r in csp_sites) / max(len(csp_sites), 1), 1
        ),
    }
    if len(csp_sites) > 0:
        csp_analysis["pct_unsafe_inline"] = round(csp_analysis["uses_unsafe_inline"] / len(csp_sites) * 100, 1)
        csp_analysis["pct_unsafe_eval"] = round(csp_analysis["uses_unsafe_eval"] / len(csp_sites) * 100, 1)
        csp_analysis["pct_nonce"] = round(csp_analysis["uses_nonce"] / len(csp_sites) * 100, 1)
        csp_analysis["pct_strict_dynamic"] = round(csp_analysis["uses_strict_dynamic"] / len(csp_sites) * 100, 1)

    # CSP Observatory result distribution
    csp_results = Counter()
    for sr in scored_results:
        csp_results[sr["tests"]["csp"]["result"]] += 1
    csp_analysis["observatory_results"] = dict(csp_results.most_common())

    # HSTS analysis
    hsts_sites = [r for r in results if r.get("hsts_parsed")]
    hsts_analysis = {
        "total_with_hsts": len(hsts_sites),
        "percentage": round(len(hsts_sites) / len(results) * 100, 1),
        "with_preload": sum(1 for r in hsts_sites if r["hsts_parsed"].get("preload")),
        "with_includeSubDomains": sum(1 for r in hsts_sites if r["hsts_parsed"].get("includeSubDomains")),
        "max_age_buckets": {
            "< 1 day": sum(1 for r in hsts_sites if (r["hsts_parsed"].get("max_age") or 0) < 86400),
            "1 day - 1 month": sum(1 for r in hsts_sites if 86400 <= (r["hsts_parsed"].get("max_age") or 0) < 2592000),
            "1-6 months": sum(1 for r in hsts_sites if 2592000 <= (r["hsts_parsed"].get("max_age") or 0) < 15552000),
            "6-12 months": sum(1 for r in hsts_sites if 15552000 <= (r["hsts_parsed"].get("max_age") or 0) < 31536000),
            ">= 1 year": sum(1 for r in hsts_sites if (r["hsts_parsed"].get("max_age") or 0) >= 31536000),
        },
    }
    if len(hsts_sites) > 0:
        hsts_analysis["pct_preload"] = round(hsts_analysis["with_preload"] / len(hsts_sites) * 100, 1)
        hsts_analysis["pct_includeSubDomains"] = round(hsts_analysis["with_includeSubDomains"] / len(hsts_sites) * 100, 1)

    # HSTS Observatory result distribution
    hsts_results = Counter()
    for sr in scored_results:
        hsts_results[sr["tests"]["hsts"]["result"]] += 1
    hsts_analysis["observatory_results"] = dict(hsts_results.most_common())

    # Info leak headers
    info_leaks = {
        "x_powered_by": {
            "count": sum(1 for r in results if r.get("headers", {}).get("x-powered-by")),
            "percentage": round(sum(1 for r in results if r.get("headers", {}).get("x-powered-by")) / len(results) * 100, 1),
        },
        "server": {
            "count": sum(1 for r in results if r.get("headers", {}).get("server")),
            "percentage": round(sum(1 for r in results if r.get("headers", {}).get("server")) / len(results) * 100, 1),
        },
    }

    # Top server header values
    server_values = Counter()
    for r in results:
        sv = r.get("headers", {}).get("server")
        if sv:
            sv_lower = sv.lower()
            if "cloudflare" in sv_lower:
                server_values["Cloudflare"] += 1
            elif "nginx" in sv_lower:
                server_values["nginx"] += 1
            elif "apache" in sv_lower:
                server_values["Apache"] += 1
            elif "microsoft" in sv_lower or "iis" in sv_lower:
                server_values["Microsoft-IIS"] += 1
            elif "gws" in sv_lower or "gse" in sv_lower:
                server_values["Google"] += 1
            elif "amazons3" in sv_lower or "amazonS3" in sv:
                server_values["AmazonS3"] += 1
            elif "openresty" in sv_lower:
                server_values["OpenResty"] += 1
            else:
                server_values["Other"] += 1
    info_leaks["top_servers"] = dict(server_values.most_common(10))

    # Adoption by rank tiers
    rank_tiers = {
        "Top 100": {"range": (1, 100), "results": [], "scored": []},
        "101-1000": {"range": (101, 1000), "results": [], "scored": []},
        "1001-5000": {"range": (1001, 5000), "results": [], "scored": []},
        "5001-10000": {"range": (5001, 10000), "results": [], "scored": []},
    }

    for r, sr in zip(results, scored_results):
        rank = r.get("rank", 99999)
        for tier_name, tier_data in rank_tiers.items():
            low, high = tier_data["range"]
            if low <= rank <= high:
                tier_data["results"].append(r)
                tier_data["scored"].append(sr)
                break

    by_rank_tier = {}
    for tier_name, tier_data in rank_tiers.items():
        tier_results = tier_data["results"]
        tier_scored = tier_data["scored"]
        if not tier_results:
            continue
        tier_adoption = {}
        for h in SCORED_HEADERS:
            count = sum(1 for r in tier_results if r.get("headers", {}).get(h))
            tier_adoption[h] = round(count / len(tier_results) * 100, 1)
        tier_grades = Counter(sr["grade"] for sr in tier_scored)
        tier_scores = [sr["score"] for sr in tier_scored]
        by_rank_tier[tier_name] = {
            "count": len(tier_results),
            "avg_score": round(sum(tier_scores) / len(tier_scores), 1),
            "median_score": sorted(tier_scores)[len(tier_scores) // 2],
            "adoption": tier_adoption,
            "grades": {g: tier_grades.get(g, 0) for g in ALL_GRADES if tier_grades.get(g, 0) > 0},
        }

    # Top/bottom scoring sites
    scored_sorted = sorted(scored_results, key=lambda x: x["score"], reverse=True)
    top_20 = [{"url": s["url"], "rank": s["rank"], "score": s["score"], "grade": s["grade"]} for s in scored_sorted[:20]]
    bottom_20 = [{"url": s["url"], "rank": s["rank"], "score": s["score"], "grade": s["grade"]} for s in scored_sorted[-20:]]

    # Zero-score sites
    zero_score_count = sum(1 for sr in scored_results if sr["score"] == 0)
    zero_score_pct = round(zero_score_count / len(results) * 100, 1)

    # 2023 vs 2026 comparison data (Ruge et al. arXiv:2410.14924)
    comparison_2023 = {
        "source": "Ruge et al. (2024), arXiv:2410.14924",
        "scan_year": 2023,
        "sample_size": 3195,
        "avg_score": 26.2,
        "f_grade_pct": 55.6,
        "zero_score_pct": 32.7,
        "note": "Used full Observatory including cookies, SRI, CORS. Max score ~135."
    }

    # Group grades into buckets for comparison
    grade_bucket_a = sum(grade_distribution[g]["percentage"] for g in ["A+", "A", "A-"])
    grade_bucket_b = sum(grade_distribution[g]["percentage"] for g in ["B+", "B", "B-"])
    grade_bucket_c = sum(grade_distribution[g]["percentage"] for g in ["C+", "C", "C-"])
    grade_bucket_d = sum(grade_distribution[g]["percentage"] for g in ["D+", "D", "D-"])
    grade_bucket_f = grade_distribution["F"]["percentage"]

    output = {
        "metadata": {
            "generated_at": __import__("datetime").datetime.now().isoformat(),
            "scoring_method": "Mozilla Observatory-compatible (base 100, modifier per test)",
            "scoring_note": "Cookies, SRI, CORS tests assigned neutral (0) as HEAD requests cannot evaluate these. Actual Observatory scores may differ.",
            "observatory_source": "https://github.com/mozilla/http-observatory/blob/main/httpobs/docs/scoring.md",
            "total_scanned": raw["metadata"].get("total_scanned", raw["metadata"].get("scanned", len(results))),
            "total_successful": len(results),
            "total_failed": raw["metadata"].get("failed", 0),
            "success_rate": round(len(results) / max(raw["metadata"].get("total_scanned", raw["metadata"].get("scanned", len(results))), 1) * 100, 1),
        },
        "score_statistics": {
            "average": avg_score,
            "median": median_score,
            "min": min(scores),
            "max": max(scores),
            "std_dev": round((sum((s - avg_score) ** 2 for s in scores) / len(scores)) ** 0.5, 1),
        },
        "key_findings": {
            "avg_score": avg_score,
            "median_score": median_score,
            "csp_adoption_pct": adoption["content-security-policy"]["percentage"],
            "hsts_adoption_pct": adoption["strict-transport-security"]["percentage"],
            "best_adopted_header": max(SCORED_HEADERS, key=lambda h: adoption[h]["percentage"]),
            "best_adopted_pct": max(adoption[h]["percentage"] for h in SCORED_HEADERS),
            "worst_adopted_header": min(SCORED_HEADERS, key=lambda h: adoption[h]["percentage"]),
            "worst_adopted_pct": min(adoption[h]["percentage"] for h in SCORED_HEADERS),
            "grade_a_plus_pct": grade_distribution["A+"]["percentage"],
            "grade_a_pct": grade_bucket_a,
            "grade_f_pct": grade_bucket_f,
            "zero_score_count": zero_score_count,
            "zero_score_pct": zero_score_pct,
            "sites_with_zero_headers": sum(
                1 for r in results
                if not any(r.get("headers", {}).get(h) for h in SCORED_HEADERS)
            ),
        },
        "grade_buckets": {
            "A": grade_bucket_a,
            "B": grade_bucket_b,
            "C": grade_bucket_c,
            "D": grade_bucket_d,
            "F": grade_bucket_f,
        },
        "comparison_2023": comparison_2023,
        "adoption_rates": adoption,
        "grade_distribution": grade_distribution,
        "csp_analysis": csp_analysis,
        "hsts_analysis": hsts_analysis,
        "info_leaks": info_leaks,
        "by_rank_tier": by_rank_tier,
        "top_20_sites": top_20,
        "bottom_20_sites": bottom_20,
    }

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"\nStudy data written to {OUTPUT}")
    print(f"  Scoring: Mozilla Observatory-compatible (base 100)")
    print(f"  Sites analyzed: {len(results)}")
    print(f"  Average score: {avg_score}/100 (median: {median_score})")
    print(f"  CSP adoption: {adoption['content-security-policy']['percentage']}%")
    print(f"  HSTS adoption: {adoption['strict-transport-security']['percentage']}%")
    print(f"  Best adopted: {output['key_findings']['best_adopted_header']} ({output['key_findings']['best_adopted_pct']}%)")
    print(f"  Grade distribution:")
    for g in ALL_GRADES:
        if grade_distribution[g]["count"] > 0:
            print(f"    {g}: {grade_distribution[g]['count']} ({grade_distribution[g]['percentage']}%)")


if __name__ == "__main__":
    main()
