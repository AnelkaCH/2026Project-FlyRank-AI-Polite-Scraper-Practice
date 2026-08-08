"""Stage 2: crawl the first three catalogue pages and collect unique book URLs."""
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

REPO_URL = "https://github.com/AnelkaCH/2026Project-FlyRank-AI-Polite-Scraper-Practice"
USER_AGENT = f"FlyRankInternshipA9/1.0 (+{REPO_URL})"
TIMEOUT = 10
REQUEST_DELAY = 0.5
MAX_PAGES = 3
FIRST_CATALOGUE_URL = "https://books.toscrape.com/catalogue/page-1.html"

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "cache"


def cache_file_for(page_number: int) -> Path:
    return CACHE_DIR / f"catalogue-page-{page_number}.html"


def fetch_page(page_url: str, cache_file: Path) -> str:
    if cache_file.exists():
        html = cache_file.read_bytes().decode("utf-8")
        print(f"CACHE HIT {cache_file.name} ({len(html)} chars)")
        return html

    time.sleep(REQUEST_DELAY)
    response = requests.get(
        page_url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT
    )
    if response.status_code != 200:
        print(f"FAILED FETCH: {page_url} status {response.status_code}")
        raise SystemExit(1)

    CACHE_DIR.mkdir(exist_ok=True)
    cache_file.write_bytes(response.content)
    html = response.content.decode("utf-8")
    print(f"FETCH {cache_file.name} ({len(response.content)} bytes)")
    return html


def collect_book_urls(page_url: str, html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    return [
        urljoin(page_url, a["href"])
        for a in soup.select("article.product_pod h3 a[href]")
    ]


def main() -> int:
    book_urls: list[str] = []
    catalogue_pages = 0
    page_url = FIRST_CATALOGUE_URL
    page_number = 1

    while page_url and catalogue_pages < MAX_PAGES:
        html = fetch_page(page_url, cache_file_for(page_number))
        book_urls.extend(collect_book_urls(page_url, html))

        soup = BeautifulSoup(html, "html.parser")
        next_link = soup.select_one("li.next a[href]")
        page_url = urljoin(page_url, next_link["href"]) if next_link else None

        catalogue_pages += 1
        page_number += 1

    unique_urls = set(book_urls)
    print(
        f"catalogue_pages={catalogue_pages}, "
        f"discovered={len(book_urls)}, unique_urls={len(unique_urls)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
