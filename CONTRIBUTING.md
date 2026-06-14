# Contributing

Thanks for your interest in improving Summer School Radar.

## Ways to Contribute

- **Submit an opportunity**: open an issue with the [submit-opportunity template](.github/ISSUE_TEMPLATE/submit-opportunity.yml). Maintainers review submissions and add high-confidence records to `data/opportunities.yml`.
- **Add or fix a trusted source**: edit `config/sources.yaml`. Each source needs a `name`, `url`, `layer`, `region`, `source_type`, and `keywords`. If a source is unreachable for scripted requests, keep it in the registry with `enabled: false` and a note explaining why, so coverage stays transparent.
- **Improve extraction or filtering**: the rule-based pipeline lives in `src/research_school_radar/`. Please add a test for every behavioural change.
- **Improve the website or reports**: `site.py` renders the static site, `report.py` renders the Markdown reports.

## Development Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

Run the test suite:

```powershell
pytest
```

Run a full offline check without any network access:

```powershell
python -m research_school_radar.cli scan --offline-sample
```

## Pull Request Guidelines

- Keep changes focused; one concern per pull request.
- All tests must pass (`pytest`). CI runs them automatically on every push and pull request.
- Near-matches must never be presented as fully qualified opportunities — this is the core trust guarantee of the project. Changes that weaken hard filters need a clear justification.
- For new extraction rules, include at least one test with realistic page text.

## Curated Records

`data/opportunities.yml` is the maintainer-reviewed layer. Records there must have been manually verified against the official page, including deadline, funding evidence, and fee. The schema is documented in the file header.
