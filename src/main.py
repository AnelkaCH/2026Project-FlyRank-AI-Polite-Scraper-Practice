"""Stage 4: validate every record against the schema and write books.json."""
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from pydantic import ValidationError

from models import BookRecord, PriceParseError, parse_price

REPO_URL = "https://github.com/AnelkaCH/2026Project-FlyRank-AI-Polite-Scraper-Practice"
USER_AGENT = f"FlyRankInternshipA9/1.0 (+{REPO_URL})"
TIMEOUT = 10
REQUEST_DELAY = 0.5
MAX_PAGES = 3
FIRST_CATALOGUE_URL = "https://books.toscrape.com/catalogue/page-1.html"

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "cache"
OUTPUT_DIR = ROOT / "output"

sys.stdout.reconfigure(encoding="utf-8")


def cache_file_for(page_number: int) -> Path:
    return CACHE_DIR / f"catalogue-page-{page_number}.html"


def book_cache_file(book_url: str) -> Path:
    slug = urlparse(book_url).path.rstrip("/").split("/")[-2]
    return CACHE_DIR / f"{slug}.html"


def fetch_page(page_url: str, cache_file: Path) -> str:
    if cache_file.exists():
        html = cache_file.read_bytes().decode("utf-8")
        print(f"CACHE HIT {cache_file.name} ({cache_file.stat().st_size} bytes)")
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


def parse_book_record(
    html: str, book_url: str, source_page: str, fetched_at: str
) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    product = soup.select_one("div.product_main")

    title = product.select_one("h1").text.strip()

    price = product.select_one("p.price_color")
    price_text = price.text.strip() if price else None

    availability = product.select_one("p.instock.availability")
    availability_text = (
        " ".join(availability.text.split()) if availability else None
    )

    rating = product.select_one("p.star-rating")
    rating_text = None
    if rating is not None:
        rating_text = next(
            (c for c in rating.get("class", []) if c != "star-rating"), None
        )

    description = None
    desc_heading = soup.select_one("#product_description")
    if desc_heading is not None:
        desc_paragraph = desc_heading.find_next_sibling("p")
        if desc_paragraph is not None:
            description = desc_paragraph.text.strip()

    return {
        "title": title,
        "product_url": book_url,
        "price_text": price_text,
        "availability_text": availability_text,
        "rating_text": rating_text,
        "description": description,
        "source_page": source_page,
        "fetched_at": fetched_at,
    }


def iso_utc(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def build_finished_record(raw: dict) -> dict:
    return {
        **raw,
        "price_gbp": parse_price(raw.get("price_text")),
    }


def main() -> int:
    sources: dict[str, str] = {}
    catalogue_pages = 0
    page_url = FIRST_CATALOGUE_URL
    page_number = 1

    while page_url and catalogue_pages < MAX_PAGES:
        html = fetch_page(page_url, cache_file_for(page_number))
        for book_url in collect_book_urls(page_url, html):
            sources[book_url] = page_url

        soup = BeautifulSoup(html, "html.parser")
        next_link = soup.select_one("li.next a[href]")
        page_url = urljoin(page_url, next_link["href"]) if next_link else None

        catalogue_pages += 1
        page_number += 1

    good_records: list[dict] = []
    bad_records: list[dict] = []
    seen_urls: set[str] = set()

    for book_url in sources:
        if book_url in seen_urls:
            continue
        seen_urls.add(book_url)

        cache_file = book_cache_file(book_url)
        html = fetch_page(book_url, cache_file)
        fetched_at = iso_utc(cache_file.stat().st_mtime)
        raw = parse_book_record(html, book_url, sources[book_url], fetched_at)

        try:
            finished = build_finished_record(raw)
            record = BookRecord.model_validate(finished)
        except (PriceParseError, ValidationError) as exc:
            bad_records.append({"record": raw, "reason": str(exc)})
            continue

        good_records.append(record.model_dump())

    OUTPUT_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / "books.json").write_text(
        json.dumps(good_records, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (OUTPUT_DIR / "errors.json").write_text(
        json.dumps(bad_records, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"books_written={len(good_records)}, errors={len(bad_records)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
