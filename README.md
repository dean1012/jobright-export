# jobright-export

[![CI](https://github.com/dean1012/jobright-export/actions/workflows/ci.yml/badge.svg)](https://github.com/dean1012/jobright-export/actions/workflows/ci.yml)

Small command-line utility for extracting selected fields from Jobright.ai job
postings and formatting them for external application-tracking workflows.

## Why?

Jobright.ai provides its own application tracking, but some users maintain a
separate master tracker for applications submitted through multiple sources.

This tool helps bridge that workflow by extracting key fields from a
Jobright.ai job posting URL and printing a tab-separated, spreadsheet-friendly
output line. The generated line is also copied to the clipboard automatically.

## Features

* Fetches Jobright.ai job posting pages directly
* Extracts the company name, job title, remote status, location, and work model
* Prints sanitized tab-separated output for easy spreadsheet import
* Copies the sanitized output line to the clipboard automatically
* Normalizes accepted URLs to the minimal Jobright.ai posting URL
* Supports repeated interactive use until `quit`, `exit`, `Ctrl+C`, or EOF
* Reports invalid, deleted, unavailable, and malformed postings without exiting
* Stops downloading a page once the required embedded job data has been found

## Requirements

* Python 3.12
* `pip`
* Internet access
* Clipboard support on your operating system

Runtime Python package dependencies are listed in `requirements.txt`.

## Installation

Clone the repository:

```bash
git clone https://github.com/dean1012/jobright-export.git
cd jobright-export
```

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install runtime dependencies:

```bash
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

Make the script executable:

```bash
chmod +x jobright-export
```

## Usage

Run the tool:

```bash
./jobright-export
```

Enter a Jobright.ai job posting URL when prompted:

```text
Jobright.ai Job Posting URL: https://jobright.ai/jobs/info/<jobid>
```

The output fields are separated by literal tab characters:

```text
companyName<TAB>jobTitle<TAB>Location<TAB>URL
```

`<TAB>` is shown in documentation to make the separator visible. The actual
output uses real tab characters so that spreadsheet applications place each
field in a separate column.

## Output Formatting

Remote postings use:

```text
Remote
```

Non-remote postings preserve the location supplied by Jobright.ai and append
the work model, such as `Onsite` or `Hybrid`:

```text
City, State workModel
```

Recognized trailing US country metadata is omitted:

```text
Houston, TX, US Hybrid
=> Houston, TX Hybrid
```

Unfamiliar or international location formats are preserved:

```text
Toronto, ON, Canada Hybrid
```

Accepted URLs are normalized to:

```text
https://jobright.ai/jobs/info/<jobid>
```

This removes `www`, trailing slashes, query parameters, and fragments from the
exported URL.

## Examples

Remote:

```text
ExampleTech Systems<TAB>Cloud Engineer<TAB>Remote<TAB>https://jobright.ai/jobs/info/<jobid>
```

Onsite:

```text
ExampleTech Systems<TAB>Systems Engineer<TAB>Austin, TX Onsite<TAB>https://jobright.ai/jobs/info/<jobid>
```

Hybrid:

```text
ExampleTech Systems<TAB>Platform Engineer<TAB>Houston, TX Hybrid<TAB>https://jobright.ai/jobs/info/<jobid>
```

Example session:

```text
$ ./jobright-export
Enter a Jobright.ai Job Posting URL to extract the company name, job title, and location. Type 'quit' or 'exit' to stop.
The extracted information will be copied to the clipboard and displayed.

Jobright.ai Job Posting URL: https://jobright.ai/jobs/info/<jobid>
ExampleTech Systems<TAB>Cloud Engineer<TAB>Remote<TAB>https://jobright.ai/jobs/info/<jobid>

Jobright.ai Job Posting URL: exit
```

## Error Handling

The prompt remains active after recoverable errors. The tool reports:

* Invalid URLs
* Missing, invalid, or deleted postings
* Jobright.ai outages, timeouts, rate limits, and server-side errors
* Unexpected page-format changes
* Clipboard failures

## Development

Install runtime and development dependencies:

```bash
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
python3 -m pip install -r requirements-dev.txt
```

Run the same validation commands used by CI:

```bash
python3 -m pip_audit --progress-spinner off -r requirements.txt
python3 -m py_compile jobright-export
mypy --strict jobright-export
ruff check jobright-export
ruff format --check jobright-export
yamllint .
markdownlint-cli2 .
```

Before committing changes, also check the current diff for whitespace errors:

```bash
git diff --check
```

CI also validates Markdown and YAML files and runs on pushes, pull requests, and
manual workflow dispatches. Dependabot checks Python packages and GitHub Actions
weekly.

## Notes

This is a small personal workflow utility. It intentionally extracts only the
fields needed for application tracking and ignores the rest of the page
content.

Because this tool depends on the Jobright.ai page structure, future site
changes may require parser updates.

## License

MIT
