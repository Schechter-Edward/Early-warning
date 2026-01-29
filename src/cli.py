#!/usr/bin/env python3
"""
One-command runner for GitHub Risk Inspector.
$ python cli.py owner/repo
"""
import argparse
import os
import sys
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from risk_engine import main  # trimmed engine


def parse_args():
    parser = argparse.ArgumentParser(description="Generate a GitHub risk report.")
    parser.add_argument("repo", nargs="?", help="Repository in owner/name format.")
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open the report in a browser.",
    )
    return parser.parse_args()


def is_ci():
    return os.getenv("CI", "").lower() in {"1", "true", "yes"}


def should_open_browser(args):
    if args.no_browser:
        return False
    return not is_ci()


def main_cli():
    args = parse_args()
    if not args.repo and is_ci():
        raise SystemExit("Missing repo argument in CI. Use: python src/cli.py owner/name")
    repo = args.repo or input("repo (owner/name): ")
    token = os.getenv("GITHUB_TOKEN", "")
    html_path = main(repo, token)

    print(f"\n📊 Opening {html_path}")
    if should_open_browser(args):
        webbrowser.open(str(html_path))


if __name__ == "__main__":
    main_cli()
