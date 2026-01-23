#!/usr/bin/env python3
"""
One-command runner for GitHub Risk Inspector.
$ python cli.py owner/repo
"""
import os, sys, json, webbrowser
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from risk_engine import main  # trimmed engine

repo = sys.argv[1] if len(sys.argv) > 1 else input("repo (owner/name): ")
token = os.getenv("GITHUB_TOKEN", "")
html_path = main(repo, token)

print(f"\n📊 Opening {html_path}")
webbrowser.open(html_path)
