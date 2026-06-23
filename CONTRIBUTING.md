# Contributing

Thank you for your interest in improving `jobright-export`.

## Development Setup

Create and activate a Python 3.12 or newer virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install runtime and development dependencies:

```bash
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
python3 -m pip install -r requirements-dev.txt
```

## Validation

Run the same validation commands used by CI:

```bash
python3 -m pip_audit --progress-spinner off -r requirements.txt
python3 -m py_compile jobright-export
python3 -m coverage run -m unittest discover -s tests -v
python3 -m coverage report
python3 -m coverage xml
mypy --strict jobright-export
ruff check jobright-export tests
ruff format --check jobright-export tests
git ls-files '*.yml' '*.yaml' | xargs -r yamllint
git ls-files '*.md' | xargs -r markdownlint-cli2
```

The coverage report measures application code and fails if coverage falls below
the 90% threshold configured in `pyproject.toml`.

CI also generates `coverage.xml` and uploads it to Codecov using GitHub Actions
OIDC authentication. No `CODECOV_TOKEN` repository secret is required.
Project coverage checks and pull request comments are configured in
`codecov.yml`.

Before committing changes, also check the current diff for whitespace errors:

```bash
git diff --check
```

## Pull Requests

Create a focused feature branch for each change. Reference the related issue in
each commit and include `Closes #<issue-number>` in the pull request
description when the pull request should close an issue after merging.

Sign each commit so GitHub can verify its authorship. The `main` branch ruleset
requires signed commits before merging:

```bash
git commit -S -m "<message> (Refs #<issue-number>)"
```

CI runs on pushes, pull requests, and manual workflow dispatches. Dependabot
checks Python packages and GitHub Actions weekly.

## Documentation Guidelines

Keep user-facing behavior documented in `README.md` and contributor workflows
documented in `CONTRIBUTING.md`. In Python code, use docstrings for module,
class, and function responsibilities. Add inline comments for non-obvious
implementation decisions, security boundaries, and assumptions. Avoid comments
that merely restate straightforward code.
