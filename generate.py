#!/usr/bin/env python3
"""
Advanced GitHub Redirect - Article Page Generator
==================================================
Scrapes metadata from target URLs and generates individual HTML pages
with rich Open Graph, Twitter Card, and Schema.org metadata.

Usage:
    python3 generate.py                  # Generate only new/missing pages
    python3 generate.py --force          # Regenerate ALL pages
    python3 generate.py --test 5         # Generate only first 5 for testing
"""

import csv
import os
import re
import sys
import json
import time
import html
import argparse
import subprocess
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============================================================
# CONFIG — Change these for different projects
# ============================================================
CSV_FILE = "articles.csv"
OUTPUT_DIR = "."  # Root of the GitHub Pages repo
GITHUB_PAGES_DOMAIN = "easy-recipes322.github.io/easy-recipes323"  # Change for each project
# ============================================================


def fetch_page(url, retries=2):
    """Fetch a URL using curl and return the HTML content."""
    for attempt in range(retries + 1):
        try:
            result = subprocess.run(
                ["curl", "-s", "-L", "--max-time", "15",
                 "-A", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36",
                 url],
                capture_output=True, text=True, timeout=20
            )
            if result.returncode == 0 and result.stdout:
                return result.stdout
        except Exception as e:
            if attempt < retries:
                time.sleep(1)
            else:
                print(f"  ✗ Failed to fetch {url}: {e}")
                return None
    print(f"  ✗ Failed to fetch {url} after {retries + 1} attempts")
    return None


def download_image(url, save_path, retries=2):
    """Download an image file using curl."""
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    for attempt in range(retries + 1):
        try:
            result = subprocess.run(
                ["curl", "-s", "-L", "--max-time", "30", "-o", save_path, url],
                capture_output=True, timeout=35
            )
            if result.returncode == 0 and os.path.exists(save_path) and os.path.getsize(save_path) > 100:
                return True
        except Exception:
            if attempt < retries:
                time.sleep(1)
    return False


def extract_meta(html_content):
    """Extract all relevant metadata from HTML content."""
    meta = {}

    # Title
    m = re.search(r"<title[^>]*>(.*?)</title>", html_content, re.DOTALL | re.IGNORECASE)
    if m:
        meta["title"] = html.unescape(m.group(1).strip())

    # Meta description
    m = re.search(r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']', html_content, re.IGNORECASE | re.DOTALL)
    if m:
        meta["description"] = html.unescape(m.group(1).strip())

    # OG tags
    og_pattern = r'<meta\s+property=["\'](og:[^"\']+)["\']\s+content=["\'](.*?)["\']'
    for match in re.finditer(og_pattern, html_content, re.IGNORECASE | re.DOTALL):
        meta[match.group(1)] = html.unescape(match.group(2).strip())

    # Article tags
    article_pattern = r'<meta\s+property=["\'](article:[^"\']+)["\']\s+content=["\'](.*?)["\']'
    for match in re.finditer(article_pattern, html_content, re.IGNORECASE | re.DOTALL):
        meta[match.group(1)] = html.unescape(match.group(2).strip())

    # Twitter tags
    twitter_pattern = r'<meta\s+name=["\'](twitter:[^"\']+)["\']\s+content=["\'](.*?)["\']'
    for match in re.finditer(twitter_pattern, html_content, re.IGNORECASE | re.DOTALL):
        meta[match.group(1)] = html.unescape(match.group(2).strip())

    # JSON-LD Schema (Recipe, Article, etc.)
    jsonld_pattern = r'<script\s+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>'
    schemas = []
    for match in re.finditer(jsonld_pattern, html_content, re.DOTALL | re.IGNORECASE):
        try:
            data = json.loads(match.group(1).strip())
            schemas.append(data)
        except json.JSONDecodeError:
            pass
    if schemas:
        meta["_schemas"] = schemas

    return meta


def encode_url_chars(url):
    """Encode a URL as JavaScript char codes for obfuscation."""
    return "[" + ",".join(str(ord(c)) for c in url) + "]"


def replace_domain_in_schema(schema, old_domain, new_base_url, image_map):
    """Recursively replace the old domain in all schema URLs and image paths."""
    if isinstance(schema, dict):
        new_dict = {}
        for key, value in schema.items():
            new_dict[key] = replace_domain_in_schema(value, old_domain, new_base_url, image_map)
        return new_dict
    elif isinstance(schema, list):
        return [replace_domain_in_schema(item, old_domain, new_base_url, image_map) for item in schema]
    elif isinstance(schema, str):
        # Check if this URL matches a downloaded image
        for original_url, local_url in image_map.items():
            if value_matches_url(schema, original_url):
                return local_url
        # Replace domain in @id, url, item, and other URL fields
        if old_domain in schema:
            return schema.replace(f"https://{old_domain}", new_base_url).replace(f"http://{old_domain}", new_base_url)
        return schema
    else:
        return schema


def value_matches_url(value, url):
    """Check if a string value is the given URL (exact or with size suffix)."""
    if not isinstance(value, str) or not isinstance(url, str):
        return False
    # Exact match
    if value == url:
        return True
    # Match resized versions (e.g., image-500x500.png matches image.png)
    base, ext = os.path.splitext(url)
    if value.startswith(base) and value.endswith(ext):
        return True
    return False


def generate_article_html(slug, target_url, meta, github_domain, local_image_path=None):
    """Generate the HTML content for an article page."""
    title = meta.get("title", "Easy Recipes")
    description = meta.get("description", "")
    og_image_width = meta.get("og:image:width", "")
    og_image_height = meta.get("og:image:height", "")
    og_type = meta.get("og:type", "article")
    og_locale = meta.get("og:locale", "en_US")
    twitter_card = meta.get("twitter:card", "summary_large_image")
    published_time = meta.get("article:published_time", "")
    modified_time = meta.get("article:modified_time", "")

    canonical_url = f"https://{github_domain}{slug}"
    encoded_target = encode_url_chars(target_url)

    # Use local image URL if available
    og_image = ""
    if local_image_path:
        og_image = f"https://{github_domain}/{local_image_path}"

    # Extract the target domain to replace in schemas
    parsed_target = urlparse(target_url)
    target_domain = parsed_target.netloc  # e.g. "schnellrezept.com"

    # Build image map for schema replacement
    image_map = {}
    original_og_image = meta.get("og:image", "")
    if original_og_image and og_image:
        image_map[original_og_image] = og_image

    # Build meta tags
    meta_tags = f'''    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="referrer" content="no-referrer">
    <title>{html.escape(title)}</title>
    <meta name="description" content="{html.escape(description)}" />
    <meta name="robots" content="max-image-preview:large" />
    <link rel="canonical" href="{html.escape(canonical_url)}" />

    <meta property="og:locale" content="{html.escape(og_locale)}" />
    <meta property="og:site_name" content="Easy Recipes" />
    <meta property="og:type" content="{html.escape(og_type)}" />
    <meta property="og:title" content="{html.escape(title)}" />
    <meta property="og:description" content="{html.escape(description)}" />
    <meta property="og:url" content="{html.escape(canonical_url)}" />'''

    if og_image:
        meta_tags += f'''
    <meta property="og:image" content="{html.escape(og_image)}" />
    <meta property="og:image:secure_url" content="{html.escape(og_image)}" />'''
        if og_image_width:
            meta_tags += f'''
    <meta property="og:image:width" content="{html.escape(og_image_width)}" />'''
        if og_image_height:
            meta_tags += f'''
    <meta property="og:image:height" content="{html.escape(og_image_height)}" />'''

    if published_time:
        meta_tags += f'''
    <meta property="article:published_time" content="{html.escape(published_time)}" />'''
    if modified_time:
        meta_tags += f'''
    <meta property="article:modified_time" content="{html.escape(modified_time)}" />'''

    meta_tags += f'''

    <meta name="twitter:card" content="{html.escape(twitter_card)}" />
    <meta name="twitter:title" content="{html.escape(title)}" />
    <meta name="twitter:description" content="{html.escape(description)}" />'''

    if og_image:
        meta_tags += f'''
    <meta name="twitter:image" content="{html.escape(og_image)}" />'''

    # JSON-LD schemas — replace target domain with GitHub domain
    schema_tags = ""
    schemas = meta.get("_schemas", [])
    new_base_url = f"https://{github_domain}"
    for schema in schemas:
        cleaned_schema = replace_domain_in_schema(schema, target_domain, new_base_url, image_map)
        schema_str = json.dumps(cleaned_schema, ensure_ascii=False)
        # Remove any remaining target domain name fragments from filenames (e.g. "schnellrezeptlogo" → "logo")
        domain_name = target_domain.replace(".com", "").replace(".net", "").replace(".org", "").replace(".de", "")
        schema_str = schema_str.replace(domain_name, "")
        schema_tags += f'''
    <script type="application/ld+json">{schema_str}</script>'''

    # Obfuscated redirect script with bot detection + delay
    # Crawlers that execute JS (Google Rich Results) won't redirect
    # Use specific bot UA strings to avoid blocking in-app browsers (e.g. Pinterest app)
    bot_regex = "var _b=/googlebot|bingbot|yandexbot|baiduspider|facebookexternalhit|pinterestbot|whatsapp|slurp|crawl|spider|preview|headless|phantom|puppet|lighthouse|APIs-Google|AdsBot|Mediapartners/i;"
    js_parts = []
    js_parts.append("(function(){")
    js_parts.append("var _ua=navigator.userAgent||'';")
    js_parts.append(bot_regex)
    js_parts.append("if(_b.test(_ua))return;")
    js_parts.append("setTimeout(function(){try{")
    js_parts.append("var _c=" + encoded_target + ";")
    js_parts.append("var _u='';for(var i=0;i<_c.length;i++){_u+=String.fromCharCode(_c[i]);}")
    js_parts.append("var _s=window.location.search;if(_s)_u+=_s;")
    js_parts.append("window.location.href=_u;")
    js_parts.append("}catch(e){}},10);")
    js_parts.append("})();")
    js_code = "".join(js_parts)
    redirect_script = "\n    <script>\n        " + js_code + "\n    </script>"

    # Build page body (fallback content for bots/no-JS)
    img_tag = ""
    if og_image:
        img_tag = f'<img src="{html.escape(og_image)}" alt="{html.escape(title)}" style="max-width:100%;height:auto;border-radius:12px;margin:20px 0;" />'

    page_html = f'''<!DOCTYPE html>
<html lang="en">
<head>
{meta_tags}
{schema_tags}
{redirect_script}
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 720px;
            margin: 40px auto;
            padding: 0 20px;
            color: #333;
            line-height: 1.7;
            background: #FAFAF8;
        }}
        h1 {{
            font-size: 2rem;
            color: #1a1a1a;
            line-height: 1.3;
        }}
        p {{
            font-size: 1.05rem;
            color: #555;
        }}
        .loading {{
            text-align: center;
            padding: 40px;
            color: #999;
            font-size: 0.95rem;
        }}
    </style>
</head>
<body>
    <h1>{html.escape(title)}</h1>
    {img_tag}
    <p>{html.escape(description)}</p>
    <p class="loading">Loading full recipe...</p>
</body>
</html>'''

    return page_html


def process_article(slug, target_url, output_dir, github_domain, force=False):
    """Process a single article: fetch metadata, download image, and generate HTML."""
    # Determine output path
    clean_slug = slug.strip("/")
    out_path = os.path.join(output_dir, clean_slug, "index.html")

    # Skip if already exists (unless force)
    if os.path.exists(out_path) and not force:
        return ("skipped", slug)

    # Fetch page
    html_content = fetch_page(target_url)
    if not html_content:
        return ("failed", slug)

    # Extract metadata
    meta = extract_meta(html_content)
    if not meta.get("title"):
        return ("failed", slug)

    # Download the main image locally
    local_image_path = None
    og_image = meta.get("og:image", "")
    if og_image:
        # Get image filename from URL
        parsed_img = urlparse(og_image)
        img_filename = os.path.basename(parsed_img.path)
        if img_filename:
            # Save to article directory: en/slug/image.png
            local_save = os.path.join(output_dir, clean_slug, img_filename)
            if download_image(og_image, local_save):
                local_image_path = f"{clean_slug}/{img_filename}"

    # Generate HTML
    page_html = generate_article_html(slug, target_url, meta, github_domain, local_image_path)

    # Write file
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(page_html)

    return ("ok", slug)


def main():
    parser = argparse.ArgumentParser(description="Generate article redirect pages with rich metadata")
    parser.add_argument("--force", action="store_true", help="Regenerate all pages (not just new ones)")
    parser.add_argument("--test", type=int, default=0, help="Only process first N articles (for testing)")
    parser.add_argument("--workers", type=int, default=5, help="Number of parallel workers (default: 5)")
    parser.add_argument("--csv", type=str, default=CSV_FILE, help="Path to articles CSV")
    parser.add_argument("--output", type=str, default=OUTPUT_DIR, help="Output directory")
    parser.add_argument("--domain", type=str, default=GITHUB_PAGES_DOMAIN, help="GitHub Pages domain")
    args = parser.parse_args()

    # Read CSV
    articles = []
    with open(args.csv, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            articles.append((row["slug"], row["target_url"]))

    if args.test > 0:
        articles = articles[:args.test]

    total = len(articles)
    print(f"\n🍳 Advanced GitHub Redirect Generator")
    print(f"   Domain: {args.domain}")
    print(f"   Articles: {total}")
    print(f"   Mode: {'FORCE (regenerate all)' if args.force else 'Incremental (new only)'}")
    print(f"   Workers: {args.workers}")
    print(f"   📷 Images: downloading locally (no external references)")
    print(f"{'='*50}\n")

    ok_count = 0
    skip_count = 0
    fail_count = 0
    failed_slugs = []

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {}
        for slug, target_url in articles:
            future = executor.submit(
                process_article, slug, target_url, args.output, args.domain, args.force
            )
            futures[future] = slug

        for i, future in enumerate(as_completed(futures), 1):
            status, slug = future.result()
            if status == "ok":
                ok_count += 1
                print(f"  [{i}/{total}] ✓ {slug}")
            elif status == "skipped":
                skip_count += 1
            elif status == "failed":
                fail_count += 1
                failed_slugs.append(slug)
                print(f"  [{i}/{total}] ✗ FAILED: {slug}")

    # Summary
    print(f"\n{'='*50}")
    print(f"✅ Generated: {ok_count}")
    print(f"⏭️  Skipped (already exists): {skip_count}")
    print(f"❌ Failed: {fail_count}")
    if failed_slugs:
        print(f"\nFailed articles:")
        for s in failed_slugs:
            print(f"  - {s}")
    print(f"\nDone! Run 'git add . && git commit -m \"Update articles\" && git push' to deploy.\n")


if __name__ == "__main__":
    main()
