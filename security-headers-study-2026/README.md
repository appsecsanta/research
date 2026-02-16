# Security Headers Adoption Study 2026

**Published article:** [appsecsanta.com/research/security-headers-study-2026](https://appsecsanta.com/research/security-headers-study-2026)

## Overview

This study scans 10,000 top websites for security response headers and scores each site using the [Mozilla Observatory](https://github.com/mozilla/http-observatory) methodology. It measures adoption rates for CSP, HSTS, X-Frame-Options, and seven other security headers, with breakdowns by rank tier, grade distribution, and year-over-year comparison.

## Scoring Methodology

Base score of 100 with modifiers per test:

| Test | Range | What it checks |
|------|-------|----------------|
| Content-Security-Policy | -25 to +10 | CSP presence, unsafe-inline/eval usage |
| Strict-Transport-Security | -20 to +5 | HSTS max-age, preload directive |
| X-Frame-Options | -20 to +5 | Clickjacking protection (or CSP frame-ancestors) |
| X-Content-Type-Options | -5 to 0 | MIME sniffing prevention |
| Referrer-Policy | -5 to +5 | Referrer information leakage control |
| X-XSS-Protection | -5 to 0 | Legacy XSS filter header |
| Redirection | -20 to 0 | HTTPS enforcement |

Bonuses only apply when the base score (before bonuses) is 90 or above. Grades follow the Observatory scale from A+ to F.

**Note:** Cookie, SRI, and CORS tests are assigned a neutral score (0) because HEAD requests cannot evaluate these. Actual Observatory scores may differ slightly.

## Data Pipeline

```
scan_targets.json ─→ scan-headers.js ─→ (headers_scan_raw.json)
                                               │
                     aggregate-headers-study.py ─→ headers_study_2026.json
```

## Data Files

| File | Size | Description |
|------|------|-------------|
| `data/scan_targets.json` | 981 KB | List of 10,000 domains with rank and URL |
| `data/headers_study_2026.json` | 12 KB | Final study data: score statistics, adoption rates, grade distribution, CSP/HSTS analysis, rank-tier breakdowns, top/bottom sites |

Raw scan results (`headers_scan_raw.json`) are not included in this repo. Run the scan script to generate them locally.

## Scripts

| Script | Description |
|--------|-------------|
| `scripts/scan-headers.js` | Sends HEAD requests to each target, collects security headers, parses CSP and HSTS values. 500ms delay between requests, 10s timeout. |
| `scripts/aggregate-headers-study.py` | Applies Observatory scoring to each scan result, computes adoption rates, grade distributions, CSP/HSTS deep analysis, info leak detection, and rank-tier breakdowns. |

## Reproduce

```bash
# 1. Scan websites for security headers
node scripts/scan-headers.js

# 2. Aggregate results and compute scores
python3 scripts/aggregate-headers-study.py
```

Scan targets (`data/scan_targets.json`) are already included. The full scan takes several hours due to rate limiting.

Output: `data/headers_study_2026.json`

## Known Limitations

- HEAD requests may return different headers than GET in some edge cases.
- Cookie, SRI, and CORS scoring is not possible without full page loads.
- Scan targets are based on publicly available top-sites rankings and may not perfectly reflect current traffic.
- Some sites block automated requests or return different headers based on User-Agent.
- This is a point-in-time snapshot from February 2026.
