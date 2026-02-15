#!/usr/bin/env python3
"""Check Docker Hub for new server image tags and open GitHub issues."""

import argparse
import json
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path

KNOWN_SDKS = Path(__file__).resolve().parent.parent / "known-sdks.json"
DOCKER_HUB_TAGS_URL = (
    "https://hub.docker.com/v2/repositories/{image}/tags/"
    "?page_size=10&ordering=last_updated"
)


def load_servers():
    with open(KNOWN_SDKS) as f:
        data = json.load(f)
    return data.get("server_benchmarks", [])


def fetch_latest_tags(image: str) -> list[str]:
    """Return up to 10 most-recently-updated tags from Docker Hub."""
    url = DOCKER_HUB_TAGS_URL.format(image=image)
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
    except urllib.error.URLError as exc:
        print(f"  WARNING: could not reach Docker Hub for {image}: {exc}", file=sys.stderr)
        return []
    return [r["name"] for r in data.get("results", [])]


def existing_issue_titles() -> set[str]:
    """Return titles of open issues in this repo (requires gh CLI)."""
    try:
        out = subprocess.run(
            ["gh", "issue", "list", "--state", "open", "--limit", "200", "--json", "title"],
            capture_output=True, text=True, check=True,
        )
        return {issue["title"] for issue in json.loads(out.stdout)}
    except (subprocess.CalledProcessError, FileNotFoundError):
        return set()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would be created without opening issues",
    )
    args = parser.parse_args()

    servers = load_servers()
    open_titles = existing_issue_titles()

    for server in servers:
        if not server.get("enabled"):
            continue
        image = server["docker_image"]
        name = server["name"]
        print(f"Checking {name} ({image})...")

        tags = fetch_latest_tags(image)
        if not tags:
            continue

        for tag in tags:
            title = f"[Server Update] {name} \u2014 new tag: {tag}"
            if title in open_titles:
                continue

            if args.dry_run:
                print(f"  Would create issue: {title}")
            else:
                print(f"  Creating issue: {title}")
                subprocess.run(
                    ["gh", "issue", "create", "--title", title, "--body",
                     f"Docker Hub image `{image}:{tag}` has a new tag.\n\n"
                     f"Please review and update the adapter if needed."],
                    check=True,
                )
            # Only open an issue for the most recent new tag per server
            break


if __name__ == "__main__":
    main()
