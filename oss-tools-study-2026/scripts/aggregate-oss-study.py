#!/usr/bin/env python3
"""Aggregate GitHub + download data for the Open Source AppSec Tools Study.

Reads:
  - data/oss_tools_github_raw.json
  - data/oss_tools_downloads.json

Writes:
  - data/oss_study_2026.json
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
GITHUB_FILE = DATA_DIR / "oss_tools_github_raw.json"
DOWNLOADS_FILE = DATA_DIR / "oss_tools_downloads.json"
OUTPUT_FILE = DATA_DIR / "oss_study_2026.json"


def compute_health_score(gh):
    """Compute a 0-100 health score from GitHub metrics."""
    if not gh:
        return 0

    score = 0

    # Recency of last push (max 25 points)
    pushed = gh.get("pushed_at")
    if pushed:
        days_since = (datetime.now(timezone.utc) - datetime.fromisoformat(pushed.replace("Z", "+00:00"))).days
        if days_since <= 7:
            score += 25
        elif days_since <= 30:
            score += 20
        elif days_since <= 90:
            score += 15
        elif days_since <= 180:
            score += 10
        elif days_since <= 365:
            score += 5

    # Commit activity (max 25 points)
    activity = gh.get("commit_activity")
    if activity:
        monthly = activity.get("last_1_month", 0)
        if monthly >= 50:
            score += 25
        elif monthly >= 20:
            score += 20
        elif monthly >= 10:
            score += 15
        elif monthly >= 5:
            score += 10
        elif monthly >= 1:
            score += 5

    # Release cadence (max 20 points)
    releases = gh.get("releases")
    if releases:
        yearly = releases.get("releases_last_year", 0)
        if yearly >= 12:
            score += 20
        elif yearly >= 6:
            score += 15
        elif yearly >= 3:
            score += 10
        elif yearly >= 1:
            score += 5

    # Contributors (max 15 points)
    contribs = gh.get("contributor_count", 0) or 0
    if contribs >= 100:
        score += 15
    elif contribs >= 50:
        score += 12
    elif contribs >= 20:
        score += 9
    elif contribs >= 10:
        score += 6
    elif contribs >= 3:
        score += 3

    # Issue response (max 15 points)
    issues = gh.get("issue_stats")
    if issues and issues.get("median_close_days") is not None:
        median = issues["median_close_days"]
        if median <= 1:
            score += 15
        elif median <= 7:
            score += 12
        elif median <= 30:
            score += 9
        elif median <= 90:
            score += 5

    return min(score, 100)


def main():
    if not GITHUB_FILE.exists():
        print(f"ERROR: {GITHUB_FILE} not found. Run collect-github-data.js first.")
        sys.exit(1)

    github_data = json.load(open(GITHUB_FILE))
    downloads_data = {}
    if DOWNLOADS_FILE.exists():
        dl = json.load(open(DOWNLOADS_FILE))
        downloads_data = {t["slug"]: t.get("downloads") for t in dl.get("tools", [])}

    tools = []
    categories = {}
    languages = {}
    licenses = {}
    total_stars = 0
    total_forks = 0

    for t in github_data.get("tools", []):
        gh = t.get("github")
        if not gh:
            continue

        health = compute_health_score(gh)
        dl = downloads_data.get(t["slug"]) or {}

        tool_entry = {
            "slug": t["slug"],
            "name": t["name"],
            "category": t["category"],
            "license_frontmatter": t.get("license", "unknown"),
            "stars": gh["stars"],
            "forks": gh["forks"],
            "watchers": gh.get("watchers", 0),
            "open_issues": gh.get("open_issues", 0),
            "language": gh.get("language"),
            "github_license": gh.get("license"),
            "created_at": gh.get("created_at"),
            "pushed_at": gh.get("pushed_at"),
            "archived": gh.get("archived", False),
            "contributor_count": gh.get("contributor_count"),
            "commits_last_year": (gh.get("commit_activity") or {}).get("total_last_year"),
            "commits_last_month": (gh.get("commit_activity") or {}).get("last_1_month"),
            "releases_last_year": (gh.get("releases") or {}).get("releases_last_year"),
            "latest_release": (gh.get("releases") or {}).get("latest"),
            "issue_median_close_days": (gh.get("issue_stats") or {}).get("median_close_days"),
            "npm_monthly": dl.get("npm_monthly"),
            "pypi_monthly": dl.get("pypi_monthly"),
            "docker_pulls": dl.get("docker_pulls"),
            "health_score": health,
        }
        tools.append(tool_entry)

        # Aggregate by category
        cat = t["category"]
        if cat not in categories:
            categories[cat] = {"tools": 0, "total_stars": 0, "avg_health": []}
        categories[cat]["tools"] += 1
        categories[cat]["total_stars"] += gh["stars"]
        categories[cat]["avg_health"].append(health)

        # Languages
        lang = gh.get("language") or "Other"
        languages[lang] = languages.get(lang, 0) + 1

        # Licenses
        lic = gh.get("license") or "Unknown"
        licenses[lic] = licenses.get(lic, 0) + 1

        total_stars += gh["stars"]
        total_forks += gh["forks"]

    # Finalize category averages
    for cat in categories:
        h = categories[cat]["avg_health"]
        categories[cat]["avg_health"] = round(sum(h) / len(h), 1) if h else 0

    # Sort tools by stars descending
    tools.sort(key=lambda x: x["stars"], reverse=True)

    # Key findings
    top_starred = tools[0] if tools else None
    fastest_growing = max(
        [t for t in tools if t.get("commits_last_month")],
        key=lambda x: x["commits_last_month"],
        default=None,
    )
    best_health = max(tools, key=lambda x: x["health_score"], default=None)
    at_risk = [t for t in tools if t["health_score"] < 20]

    output = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "total_tools": len(tools),
            "total_stars": total_stars,
            "total_forks": total_forks,
        },
        "key_findings": {
            "most_starred": {"name": top_starred["name"], "stars": top_starred["stars"]} if top_starred else None,
            "most_active": {"name": fastest_growing["name"], "commits_last_month": fastest_growing["commits_last_month"]} if fastest_growing else None,
            "healthiest": {"name": best_health["name"], "score": best_health["health_score"]} if best_health else None,
            "at_risk_count": len(at_risk),
        },
        "tools": tools,
        "by_category": categories,
        "by_language": dict(sorted(languages.items(), key=lambda x: -x[1])),
        "by_license": dict(sorted(licenses.items(), key=lambda x: -x[1])),
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Study data written to {OUTPUT_FILE}")
    print(f"  Tools analyzed: {len(tools)}")
    print(f"  Total stars: {total_stars:,}")
    if top_starred:
        print(f"  Most starred: {top_starred['name']} ({top_starred['stars']:,})")
    if best_health:
        print(f"  Healthiest: {best_health['name']} (score: {best_health['health_score']})")
    print(f"  At risk: {len(at_risk)} tools")


if __name__ == "__main__":
    main()
