from pathlib import Path

import requests

REPO_URL = "https://github.com/AnelkaCH/2026Project-FlyRank-AI-Polite-Scraper-Practice"
USER_AGENT = f"FlyRankInternshipA9/1.0 (+{REPO_URL})"
TIMEOUT = 10
CATALOGUE_URL = "https://books.toscrape.com/catalogue/page-1.html"

ROOT = Path(__file__).resolve().parent.parent
CACHE_FILE = ROOT / "cache" / "catalogue-page-1.html"


def main() -> int:
    if CACHE_FILE.exists():
        print(f"CACHE HIT ({CACHE_FILE.stat().st_size} bytes)")
        return 0

    response = requests.get(
        CATALOGUE_URL, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT
    )
    if response.status_code != 200:
        print(f"FAILED FETCH: status {response.status_code}")
        return 1

    CACHE_FILE.parent.mkdir(exist_ok=True)
    CACHE_FILE.write_bytes(response.content)
    print(f"FETCH ({len(response.content)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
