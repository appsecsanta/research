<p align="center">
  <a href="https://appsecsanta.com">
    <img src="https://appsecsanta.com/images/appsecsanta-logo.png" alt="AppSec Santa" width="200">
  </a>
</p>

<h1 align="center">AppSec Santa Research</h1>

<p align="center">
  <a href="https://appsecsanta.com">Website</a> &middot;
  <a href="https://appsecsanta.com/research">All Research</a> &middot;
  <a href="#license">License</a>
</p>

---

[AppSec Santa](https://appsecsanta.com) is an independent review and comparison platform covering 129+ application security tools across 10 categories including SAST, SCA, DAST, IaC Security, and more.

This repository contains the raw datasets, collection scripts, and aggregation code behind our published research. Everything needed to verify, reproduce, or build upon our findings is here.

## Studies

| Study | Description | Sample | Directory |
|-------|-------------|--------|-----------|
| [State of Open-Source AppSec Tools 2026](https://appsecsanta.com/research/state-of-open-source-appsec-tools-2026) | Health scores, GitHub metrics, and download statistics for open-source AppSec tools | 65 tools | [`oss-tools-study-2026/`](oss-tools-study-2026/) |
| [Security Headers Adoption 2026](https://appsecsanta.com/research/security-headers-study-2026) | Security header adoption rates scored with the Mozilla Observatory methodology | 10,000 websites | [`security-headers-study-2026/`](security-headers-study-2026/) |

Each directory has its own README with methodology details, data dictionaries, and step-by-step reproduction instructions.

## Repository Structure

```
├── oss-tools-study-2026/
│   ├── README.md
│   ├── scripts/        # Data collection & aggregation
│   └── data/           # Raw + processed datasets
│
├── security-headers-study-2026/
│   ├── README.md
│   ├── scripts/        # Header scanner & aggregation
│   └── data/           # Raw + processed datasets
│
└── LICENSE
```

## General Requirements

- Python 3.10+
- Node.js 18+

Study-specific dependencies are listed in each study's README.

## Contributing

Found an issue with our data or methodology? [Open an issue](https://github.com/appsecsanta/research/issues) and we'll look into it.

## License

[MIT](LICENSE)
