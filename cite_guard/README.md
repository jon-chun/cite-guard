# Scripts

These Python modules implement the multistage pipeline.

## Requirements
- Python 3.10+
- Optional (recommended) for best results:
  - requests
  - beautifulsoup4
  - feedparser
  - PyPDF2

If optional deps are missing, some stages will degrade gracefully (lower confidence).

## CLI
From repo root:

python3 cite-guard/scripts/refqa_cli.py --help
