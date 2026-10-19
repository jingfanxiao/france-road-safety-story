"""Build the data used by the app.

Usage (from the project root):
    python scripts/build_data.py --download          # fetch raw files (cached)
    python scripts/build_data.py --download --force  # re-download everything
    python scripts/build_data.py --prepare           # clean, join, write data/processed
    python scripts/build_data.py --quality           # data quality report
    python scripts/build_data.py --download --prepare --quality   # everything
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Make the project root importable when the script is run directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import constants as C  # noqa: E402
from utils import io, prep, quality  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--download", action="store_true", help="download raw BAAC files and boundaries")
    parser.add_argument("--prepare", action="store_true", help="build the processed parquet/geojson files")
    parser.add_argument("--quality", action="store_true", help="run the data quality checks")
    parser.add_argument("--force", action="store_true", help="ignore the local cache and download again")
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = parse_args()

    if not (args.download or args.prepare or args.quality):
        print("Nothing to do. Use --download, --prepare and/or --quality (see --help).")
        return

    if args.download:
        paths = io.download_baac(force=args.force)
        geo_path = io.download_geojson(force=args.force)
        total_mb = sum(p.stat().st_size for p in [*paths, geo_path]) / 1e6
        print(f"\n{len(paths)} BAAC files + boundaries ready in data/raw ({total_mb:.1f} MB).")

    raw = None
    if args.prepare:
        raw = prep.build_all()["raw"]
        for path in [C.ACCIDENTS_FILE, C.USERS_AGG_FILE, C.GEOJSON_FILE]:
            print(f"wrote {path.relative_to(C.ROOT_DIR)} ({path.stat().st_size / 1e6:.2f} MB)")

    if args.quality:
        checks, missing = quality.build_report(raw)
        quality.write_report(checks, missing)
        summary = quality.summarize(checks)
        print(f"quality: {summary['n_pass']} pass, {summary['n_minor']} minor, "
              f"{summary['n_warning']} warning -> {C.QUALITY_JSON_FILE.relative_to(C.ROOT_DIR)}")


if __name__ == "__main__":
    main()
