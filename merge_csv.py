#!/usr/bin/env python3
"""Merge new URLs into existing articles.csv, avoiding duplicates."""
import csv
from urllib.parse import urlparse

EXISTING = "articles.csv"
NEW_FILE = "all schnellrezept.com urls - Sheet48.csv"
OUTPUT = "articles.csv"

# Load existing slugs
existing_slugs = set()
existing_rows = []
with open(EXISTING, "r") as f:
    reader = csv.DictReader(f)
    for row in reader:
        slug = row["slug"].strip()
        existing_slugs.add(slug)
        existing_rows.append((slug, row["target_url"].strip()))

print(f"Existing articles: {len(existing_rows)}")

# Read new URLs and extract slug + target_url
new_count = 0
skipped = 0
with open(NEW_FILE, "r") as f:
    reader = csv.DictReader(f)
    for row in reader:
        url = row.get("URL", "").strip()
        if not url or "schnellrezept.com" not in url:
            continue
        # Only include /en/ articles
        parsed = urlparse(url)
        path = parsed.path.rstrip("/") + "/"
        if not path.startswith("/en/"):
            continue
        slug = path  # e.g. /en/black-bean-burgers-recipe/
        if slug in existing_slugs:
            skipped += 1
            continue
        existing_slugs.add(slug)
        existing_rows.append((slug, url))
        new_count += 1

print(f"New articles to add: {new_count}")
print(f"Duplicates skipped: {skipped}")
print(f"Total articles: {len(existing_rows)}")

# Write merged CSV
with open(OUTPUT, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["slug", "target_url"])
    for slug, target_url in existing_rows:
        writer.writerow([slug, target_url])

print(f"✅ Written to {OUTPUT}")
