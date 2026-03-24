"""Generate ids.csv for sciolyid from the downloaded images.

This maps each image file to its disease/deficiency name.
Run after scrape_images.py to create the ids.csv that sciolyid needs.

Usage:
    python scripts/generate_ids_csv.py
"""

import csv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
IMAGES_DIR = BASE_DIR / "botany-images"


def main():
    ids_csv = IMAGES_DIR / "ids.csv"
    count = 0

    with open(ids_csv, "w", newline="") as f:
        writer = csv.writer(f)
        for category_dir in sorted(IMAGES_DIR.iterdir()):
            if not category_dir.is_dir() or category_dir.name == "metadata":
                continue
            for item_dir in sorted(category_dir.iterdir()):
                if not item_dir.is_dir():
                    continue
                item_name = item_dir.name
                for img in sorted(item_dir.iterdir()):
                    if img.suffix.lower() in (".jpg", ".jpeg", ".png", ".gif"):
                        rel = f"./{img.relative_to(IMAGES_DIR)}"
                        writer.writerow([rel, item_name])
                        count += 1

    print(f"Wrote {count} entries to {ids_csv}")


if __name__ == "__main__":
    main()
