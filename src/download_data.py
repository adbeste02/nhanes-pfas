"""
Download NHANES .XPT files from the CDC.

Run from the project root:
    python src/download_data.py
    python src/download_data.py --files demo pfas bmx

Files land in data/raw/ and are gitignored. Keeping this script in the repo
instead of the data itself keeps the repository small and makes the pipeline
reproducible for anyone who clones it.
"""

import argparse
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import BASE_URL, FILES  # noqa: E402

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"

# The CDC blocks requests without a normal browser user-agent.
HEADERS = {"User-Agent": "Mozilla/5.0 (research data download)"}

# First bytes of every SAS transport (.XPT) file.
XPT_MAGIC = b"HEADER RECORD*******LIBRARY HEADER RECORD!!!!!!!"


def download(key: str, overwrite: bool = False) -> Path:
    """Download one NHANES file by its key in config.FILES."""
    if key not in FILES:
        raise KeyError(f"Unknown file key {key!r}. Options: {sorted(FILES)}")

    filename = FILES[key]
    dest = RAW_DIR / filename

    if dest.exists() and not overwrite:
        with dest.open("rb") as fh:
            valid = fh.read(len(XPT_MAGIC)) == XPT_MAGIC
        if valid:
            print(f"  {filename}: already present ({dest.stat().st_size:,} bytes)")
            return dest
        print(f"  {filename}: existing file is not a valid .XPT, re-downloading")

    url = f"{BASE_URL}/{filename}"
    print(f"  {filename}: downloading from {url}")

    response = requests.get(url, headers=HEADERS, timeout=120)
    response.raise_for_status()

    # Don't trust the status code: a wrong URL returns a "Page Not Found"
    # HTML page with status 200. Every genuine SAS transport file begins
    # with the same header text, so check for that instead.
    if not response.content.startswith(XPT_MAGIC):
        preview = response.content[:80].decode("ascii", errors="replace")
        raise RuntimeError(
            f"{filename}: the server did not return a SAS transport file "
            f"({len(response.content):,} bytes, starts with {preview!r}). "
            "The URL in config.py is probably wrong."
        )

    dest.write_bytes(response.content)
    print(f"  {filename}: saved {len(response.content):,} bytes")
    return dest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--files",
        nargs="+",
        default=["demo", "pfas"],
        help=f"Which files to fetch. Options: {sorted(FILES)}",
    )
    parser.add_argument(
        "--overwrite", action="store_true", help="Re-download files that already exist"
    )
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading to {RAW_DIR}")

    for key in args.files:
        download(key, overwrite=args.overwrite)

    print("Done.")


if __name__ == "__main__":
    main()