# State of Open-Source AppSec Tools 2026

**Published article:** [appsecsanta.com/research/state-of-open-source-appsec-tools-2026](https://appsecsanta.com/research/state-of-open-source-appsec-tools-2026)

## Overview

This study analyzes 65 open-source application security tools across GitHub activity, release cadence, community size, and package manager adoption. Each tool receives a composite health score (0-100) based on five weighted dimensions.

## Health Score Methodology

| Dimension | Weight | What it measures |
|-----------|--------|------------------|
| Recency | 25 pts | Days since last push to default branch |
| Activity | 25 pts | Commits in the last month |
| Releases | 20 pts | Number of releases in the past year |
| Community | 15 pts | Total contributor count |
| Responsiveness | 15 pts | Median time to close issues |

## Data Pipeline

```
oss_tools_repos.json ─→ collect-github-data.js ─→ oss_tools_github_raw.json
                                                          │
                        collect-downloads.js ──→ oss_tools_downloads.json
                                                          │
                        aggregate-oss-study.py ─→ oss_study_2026.json
```

## Data Files

| File | Size | Description |
|------|------|-------------|
| `data/oss_tools_repos.json` | 17 KB | Tool list with GitHub repo URLs, categories, and license types |
| `data/oss_tools_github_raw.json` | 88 KB | Raw GitHub API data: stars, forks, contributors, commit activity, releases, issue stats |
| `data/oss_tools_downloads.json` | 7 KB | npm monthly, PyPI monthly, and Docker Hub pull counts |
| `data/oss_study_2026.json` | 52 KB | Final aggregated dataset with health scores, category/language/license breakdowns, and key findings |

## Scripts

| Script | Description |
|--------|-------------|
| `scripts/collect-github-data.js` | Queries the GitHub API (via Octokit) for repo metrics, contributor counts, commit activity, releases, and issue stats |
| `scripts/collect-downloads.js` | Fetches download counts from npm, PyPI, and Docker Hub public APIs |
| `scripts/aggregate-oss-study.py` | Merges GitHub + download data, computes health scores, and generates category/language/license distributions |

## Reproduce

```bash
npm install

# 1. Collect GitHub metrics (requires a personal access token)
export GITHUB_TOKEN=ghp_...
node scripts/collect-github-data.js

# 2. Collect npm / PyPI / Docker download counts
node scripts/collect-downloads.js

# 3. Aggregate into final dataset with health scores
python3 scripts/aggregate-oss-study.py
```

The tool list (`data/oss_tools_repos.json`) is the starting input and already included.

Output: `data/oss_study_2026.json`

## Known Limitations

- GitHub commit activity data can be incomplete (the statistics API returns 202 on first request and requires polling).
- Docker Hub pull counts are cumulative and favor older tools.
- PyPI/npm downloads include CI bot traffic, not just human installs.
- Stars can be artificially inflated.
- This is a snapshot from February 2026 and will change over time.
