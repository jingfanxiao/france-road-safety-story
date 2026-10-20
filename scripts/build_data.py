"""Build the data used by the app. Run from the project root:

    python scripts/build_data.py --download          # fetch the raw files (skipped if already there)
    python scripts/build_data.py --download --force  # download everything again
    python scripts/build_data.py --prepare           # clean and join -> data/processed
    python scripts/build_data.py --quality           # data quality report
    python scripts/build_data.py --download --prepare --quality   # everything
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # so "import constants" works

import constants as C  # noqa: E402
from utils import io, prep, quality  # noqa: E402

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
parser.add_argument("--download", action="store_true", help="download raw BAAC files and boundaries")
parser.add_argument("--prepare", action="store_true", help="build the processed parquet/geojson files")
parser.add_argument("--quality", action="store_true", help="run the data quality checks")
parser.add_argument("--force", action="store_true", help="download again even if the files exist")
args = parser.parse_args()

if not (args.download or args.prepare or args.quality):
    print("Nothing to do. Use --download, --prepare and/or --quality (see --help).")

if args.download:
    paths = io.download_baac(force=args.force) + [io.download_geojson(force=args.force)]
    total_mb = sum(p.stat().st_size for p in paths) / 1e6
    print(f"\n{len(paths) - 1} BAAC files + boundaries ready in data/raw ({total_mb:.1f} MB).")

raw = None
if args.prepare:
    raw = prep.build_all()
    for path in [C.ACCIDENTS_FILE, C.USERS_AGG_FILE, C.GEOJSON_FILE]:
        print(f"wrote {path.relative_to(C.ROOT_DIR)} ({path.stat().st_size / 1e6:.2f} MB)")

if args.quality:
    if raw is None:  # --quality alone: read the raw tables here (--prepare already read them)
        raw = {table: prep.load_table(table) for table in C.TABLES}
    checks, missing = quality.build_report(raw)
    summary = quality.write_report(checks, missing)
    print(f"quality: {summary['n_pass']} pass, {summary['n_minor']} minor, "
          f"{summary['n_warning']} warning -> {C.QUALITY_JSON_FILE.relative_to(C.ROOT_DIR)}")
