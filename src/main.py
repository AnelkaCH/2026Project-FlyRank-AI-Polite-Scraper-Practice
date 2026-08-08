"""Stage 5: isolate failures per page, retry politely, write a run report."""
import argparse
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
RETRY_DELAY = 1.0
MAX_PAGES = 3
FIRST_CATALOGUE_URL = "https://books.toscrape.com/catalogue/page-1.html"
TEST_BROKEN_BOOK_URL = (
    "https://books.toscrape.com/catalogue/not-a-real-book_999999/index.html"
)

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "cache"
OUTPUT_DIR = ROOT / "output"

sys.stdout.reconfigure(encoding="utf-8")


class PageFetchError(Exception):
    pass


def cache_file_for(page_number: int) -> Path:
    return CACHE_DIR / f"catalogue-page-{page_number}.html"


def book_cache_file(book_url: str) -> Path:
    slug = urlparse(book_url).path.rstrip("/").split("/")[-2]
    return CACHE_DIR / f"{slug}.html"


def fetch_page(page_url: str, cache_file: Path, stats: dict) -> str:
    if cache_file.exists():
        stats["cache_hits"] += 1
        print(f"CACHE HIT {cache_file.name} ({cache_file.stat().st_size} bytes)")
        return cache_file.read_bytes().decode("utf-8")

    last_error: str | None = None
    for attempt in range(2):
        time.sleep(REQUEST_DELAY if attempt == 0 else RETRY_DELAY)
        try:
            response = requests.get(
                page_url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT
            )
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            continue
        except requests.RequestException as exc:
            raise PageFetchError(f"{type(exc).__name__}: {exc}") from exc

        if response.status_code == 200:
            CACHE_DIR.mkdir(exist_ok=True)
            cache_file.write_bytes(response.content)
            stats["pages_fetched"] += 1
            print(f"FETCH {cache_file.name} ({len(response.content)} bytes)")
            return response.content.decode("utf-8")

        if 500 <= response.status_code < 600:
            last_error = f"server error {response.status_code}"
            continue

        raise PageFetchError(f"status {response.status_code}")

    raise PageFetchError(f"after retry: {last_error}")


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


def iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_finished_record(raw: dict) -> dict:
    return {
        **raw,
        "price_gbp": parse_price(raw.get("price_text")),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Polite books.toscrape scraper")
    parser.add_argument(
        "--test-broken-book",
        nargs="?",
        const=TEST_BROKEN_BOOK_URL,
        default=None,
        metavar="URL",
        help="add a made-up book URL to the crawl to prove failure isolation",
    )
    args = parser.parse_args(argv)

    start_wall = time.monotonic()
    start_iso = iso_now()
    stats = {"pages_fetched": 0, "cache_hits": 0}

    sources: dict[str, str] = {}
    failed_pages: list[dict] = []
    catalogue_pages = 0
    page_url = FIRST_CATALOGUE_URL
    page_number = 1

    while page_url and catalogue_pages < MAX_PAGES:
        try:
            html = fetch_page(page_url, cache_file_for(page_number), stats)
        except PageFetchError as exc:
            failed_pages.append({"url": page_url, "reason": str(exc)})
            break

        for book_url in collect_book_urls(page_url, html):
            sources[book_url] = page_url

        soup = BeautifulSoup(html, "html.parser")
        next_link = soup.select_one("li.next a[href]")
        page_url = urljoin(page_url, next_link["href"]) if next_link else None

        catalogue_pages += 1
        page_number += 1

    book_urls = list(sources)
    if args.test_broken_book is not None:
        book_urls.append(args.test_broken_book)

    good_records: list[dict] = []
    bad_records: list[dict] = []
    seen_urls: set[str] = set()

    for book_url in book_urls:
        if book_url in seen_urls:
            continue
        seen_urls.add(book_url)

        cache_file = book_cache_file(book_url)
        try:
            html = fetch_page(book_url, cache_file, stats)
        except PageFetchError as exc:
            failed_pages.append({"url": book_url, "reason": str(exc)})
            continue

        fetched_at = iso_utc(cache_file.stat().st_mtime)
        try:
            raw = parse_book_record(
                html, book_url, sources.get(book_url, FIRST_CATALOGUE_URL), fetched_at
            )
        except Exception as exc:
            failed_pages.append({"url": book_url, "reason": f"parse error: {exc}"})
            continue

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
    (OUTPUT_DIR / "run-report.json").write_text(
        json.dumps(
            {
                "start_time": start_iso,
                "duration_seconds": round(time.monotonic() - start_wall, 3),
                "pages_fetched": stats["pages_fetched"],
                "cache_hits": stats["cache_hits"],
                "valid_records": len(good_records),
                "invalid_records": len(bad_records),
                "failed_pages": len(failed_pages),
                "failed_page_urls": [f["url"] for f in failed_pages],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(
        f"books_written={len(good_records)}, errors={len(bad_records)}, "
        f"failed_pages={len(failed_pages)}"
    )
    return 1 if failed_pages or bad_records else 0


if __name__ == "__main__":
    raise SystemExit(main())
