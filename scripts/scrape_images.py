"""Scrape plant disease/deficiency images for botanybot.

Uses iNaturalist API for infections (they're actual organisms with observations)
and Wikimedia Commons for nutrient deficiencies (symptoms, not organisms).

Usage:
    python scripts/scrape_images.py                    # scrape all
    python scripts/scrape_images.py --category infections
    python scripts/scrape_images.py --item "fire blight"
    python scripts/scrape_images.py --max-per-item 30
"""

import argparse
import csv
import hashlib
import json
import os
import sys
import time
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

# === CONFIGURATION ===

BASE_DIR = Path(__file__).resolve().parent.parent
IMAGES_DIR = BASE_DIR / "botany-images"
METADATA_DIR = IMAGES_DIR / "metadata"
TAGS_CSV = METADATA_DIR / "tags.csv"

DEFAULT_MAX_PER_ITEM = 20
REQUEST_DELAY = 1.0  # seconds between API requests

# iNaturalist taxon IDs for infections
# These are the organisms/pathogens that cause each disease
INAT_TAXA = {
    "aster yellows": {"query": "Candidatus Phytoplasma asteris", "taxon_id": None},
    "wilt": {"query": "Verticillium", "taxon_id": 54105},
    "fire blight": {"query": "Erwinia amylovora", "taxon_id": 380904},
    "chestnut blight": {"query": "Cryphonectria parasitica", "taxon_id": None},
    "late blight": {"query": "Phytophthora infestans", "taxon_id": 53860},
    "botrytis blight": {"query": "Botrytis cinerea", "taxon_id": 324263},
    "rice bacterial blight": {"query": "Xanthomonas oryzae", "taxon_id": None},
    "canker": {"query": "Nectria", "taxon_id": None},
    "crown gall": {"query": "Agrobacterium tumefaciens", "taxon_id": 485613},
    "rot": {"query": "Armillaria", "taxon_id": None},
    "anthracnose": {"query": "Colletotrichum", "taxon_id": None},
    "dutch elm disease": {"query": "Ophiostoma novo-ulmi", "taxon_id": None},
    "downy mildew": {"query": "Peronosporaceae", "taxon_id": None},
    "powdery mildew": {"query": "Erysiphaceae", "taxon_id": 55525},
    "rust": {"query": "Pucciniales", "taxon_id": 69968},
    "scab": {"query": "Venturia inaequalis", "taxon_id": None},
    "smut": {"query": "Ustilago", "taxon_id": 151803},
    "mosaic": {"query": "mosaic virus", "taxon_id": None},
    "root-knot nematode disease": {"query": "Meloidogyne", "taxon_id": None},
}

# Wikimedia Commons search terms for deficiencies (not organisms)
DEFICIENCY_SEARCHES = {
    "nitrogen deficiency": ["nitrogen deficiency plant", "nitrogen deficiency leaf"],
    "phosphorus deficiency": ["phosphorus deficiency plant", "phosphorus deficiency leaf"],
    "potassium deficiency": ["potassium deficiency plant", "potassium deficiency leaf"],
    "calcium deficiency": ["calcium deficiency plant", "calcium deficiency leaf"],
    "magnesium deficiency": ["magnesium deficiency plant", "magnesium deficiency leaf chlorosis"],
    "sulfur deficiency": ["sulfur deficiency plant", "sulfur deficiency leaf"],
}

# === HELPERS ===

def fetch_json(url):
    """Fetch JSON from a URL with proper headers."""
    req = urllib.request.Request(url, headers={
        "User-Agent": "botanybot-scraper/1.0 (Science Olympiad practice bot)",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def download_image(url, dest_path):
    """Download an image file. Returns True on success."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "botanybot-scraper/1.0",
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
            if len(data) < 5000:  # skip tiny/broken images
                return False
            if len(data) > 4_000_000:  # sciolyid limit is 4MB
                return False
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            dest_path.write_bytes(data)
            return True
    except (urllib.error.URLError, OSError, TimeoutError):
        return False


def load_downloaded_urls():
    """Load already-downloaded source URLs from tags.csv."""
    urls = set()
    if TAGS_CSV.exists():
        with open(TAGS_CSV) as f:
            reader = csv.DictReader(f)
            for row in reader:
                urls.add(row.get("source_url", ""))
    return urls


def append_tag(row):
    """Append a row to tags.csv."""
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    write_header = not TAGS_CSV.exists()
    with open(TAGS_CSV, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "downloaded_at_utc", "source_page", "source_url",
            "local_path", "raw_label", "mapped_label", "category", "taxon_id"
        ])
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def resolve_taxon_id(query):
    """Search iNaturalist for a taxon and return its ID."""
    encoded = urllib.parse.quote(query)
    url = f"https://api.inaturalist.org/v1/search?q={encoded}&sources=taxa&per_page=5"
    data = fetch_json(url)
    for result in data.get("results", []):
        record = result.get("record", {})
        if record.get("observations_count", 0) > 0:
            return record["id"]
    return None


# === SCRAPERS ===

def scrape_inat(item, category, config, max_images, downloaded_urls):
    """Scrape images from iNaturalist observations for a disease."""
    taxon_id = config.get("taxon_id")
    if not taxon_id:
        print(f"  Resolving taxon ID for '{config['query']}'...")
        taxon_id = resolve_taxon_id(config["query"])
        if not taxon_id:
            print(f"  WARNING: Could not find taxon for '{config['query']}', skipping")
            return 0
        config["taxon_id"] = taxon_id
        print(f"  Found taxon ID: {taxon_id}")

    dest_dir = IMAGES_DIR / category / item
    dest_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    page = 1
    per_page = 30

    while count < max_images:
        url = (
            f"https://api.inaturalist.org/v1/observations"
            f"?taxon_id={taxon_id}"
            f"&photos=true"
            f"&quality_grade=research,needs_id"
            f"&photo_license=cc-by,cc-by-sa,cc-by-nc,cc-by-nc-sa,cc0"
            f"&order=desc&order_by=votes"
            f"&per_page={per_page}&page={page}"
        )
        try:
            data = fetch_json(url)
        except Exception as e:
            print(f"  API error on page {page}: {e}")
            break

        results = data.get("results", [])
        if not results:
            break

        for obs in results:
            if count >= max_images:
                break
            for photo in obs.get("photos", []):
                if count >= max_images:
                    break
                # Get medium-sized image URL
                photo_url = photo.get("url", "")
                if not photo_url:
                    continue
                # iNat URLs use "square" by default, switch to "medium"
                photo_url = photo_url.replace("/square.", "/medium.")

                if photo_url in downloaded_urls:
                    continue

                ext = ".jpg"
                filename = f"{item.replace(' ', '_')}_{photo['id']}{ext}"
                dest_path = dest_dir / filename

                if download_image(photo_url, dest_path):
                    downloaded_urls.add(photo_url)
                    count += 1
                    append_tag({
                        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
                        "source_page": f"https://www.inaturalist.org/observations/{obs['id']}",
                        "source_url": photo_url,
                        "local_path": str(dest_path.relative_to(IMAGES_DIR)),
                        "raw_label": photo.get("attribution", ""),
                        "mapped_label": item,
                        "category": category,
                        "taxon_id": taxon_id,
                    })
                    print(f"  [{count}/{max_images}] {filename}")

                time.sleep(REQUEST_DELAY * 0.3)

        page += 1
        time.sleep(REQUEST_DELAY)

    return count


def scrape_wikimedia(item, category, search_terms, max_images, downloaded_urls):
    """Scrape images from Wikimedia Commons for deficiencies."""
    dest_dir = IMAGES_DIR / category / item
    dest_dir.mkdir(parents=True, exist_ok=True)

    count = 0

    for query in search_terms:
        if count >= max_images:
            break

        encoded = urllib.parse.quote(query)
        url = (
            f"https://commons.wikimedia.org/w/api.php"
            f"?action=query&list=search&srnamespace=6"
            f"&srsearch={encoded}&srinfo=totalhits"
            f"&srlimit=50&format=json"
        )

        try:
            data = fetch_json(url)
        except Exception as e:
            print(f"  Wikimedia search error: {e}")
            continue

        results = data.get("query", {}).get("search", [])

        for result in results:
            if count >= max_images:
                break

            title = result.get("title", "")
            if not title.startswith("File:"):
                continue

            # Only want image files
            lower = title.lower()
            if not any(lower.endswith(ext) for ext in (".jpg", ".jpeg", ".png")):
                continue

            # Get the actual file URL
            info_url = (
                f"https://commons.wikimedia.org/w/api.php"
                f"?action=query&titles={urllib.parse.quote(title)}"
                f"&prop=imageinfo&iiprop=url|size"
                f"&iiurlwidth=800&format=json"
            )

            try:
                info_data = fetch_json(info_url)
            except Exception:
                continue

            pages = info_data.get("query", {}).get("pages", {})
            for page_data in pages.values():
                imageinfo = page_data.get("imageinfo", [{}])
                if not imageinfo:
                    continue
                # Prefer thumbnail (800px wide) to keep file sizes reasonable
                file_url = imageinfo[0].get("thumburl") or imageinfo[0].get("url", "")
                if not file_url or file_url in downloaded_urls:
                    continue

                ext = Path(file_url).suffix or ".jpg"
                safe_title = title.replace("File:", "").replace(" ", "_")[:60]
                filename = f"{item.replace(' ', '_')}_{hashlib.md5(file_url.encode()).hexdigest()[:8]}{ext}"
                dest_path = dest_dir / filename

                if download_image(file_url, dest_path):
                    downloaded_urls.add(file_url)
                    count += 1
                    append_tag({
                        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
                        "source_page": f"https://commons.wikimedia.org/wiki/{urllib.parse.quote(title)}",
                        "source_url": file_url,
                        "local_path": str(dest_path.relative_to(IMAGES_DIR)),
                        "raw_label": safe_title,
                        "mapped_label": item,
                        "category": category,
                        "taxon_id": "",
                    })
                    print(f"  [{count}/{max_images}] {filename}")

            time.sleep(REQUEST_DELAY)

    return count


# === MAIN ===

def main():
    parser = argparse.ArgumentParser(description="Scrape plant disease images for botanybot")
    parser.add_argument("--category", choices=["deficiencies", "infections"], help="Only scrape one category")
    parser.add_argument("--item", help="Only scrape a specific item")
    parser.add_argument("--max-per-item", type=int, default=DEFAULT_MAX_PER_ITEM, help="Max images per item")
    args = parser.parse_args()

    downloaded_urls = load_downloaded_urls()
    total = 0

    if args.category != "infections":
        items = DEFICIENCY_SEARCHES
        if args.item:
            items = {k: v for k, v in items.items() if k == args.item}

        for item, search_terms in items.items():
            print(f"\n=== {item} (wikimedia) ===")
            n = scrape_wikimedia(item, "deficiencies", search_terms, args.max_per_item, downloaded_urls)
            print(f"  Downloaded {n} images")
            total += n

    if args.category != "deficiencies":
        items = INAT_TAXA
        if args.item:
            items = {k: v for k, v in items.items() if k == args.item}

        for item, config in items.items():
            print(f"\n=== {item} (iNaturalist) ===")
            n = scrape_inat(item, "infections", config, args.max_per_item, downloaded_urls)
            print(f"  Downloaded {n} images")
            total += n

    print(f"\n{'='*40}")
    print(f"Total images downloaded: {total}")
    print(f"Images stored in: {IMAGES_DIR}")


if __name__ == "__main__":
    main()
