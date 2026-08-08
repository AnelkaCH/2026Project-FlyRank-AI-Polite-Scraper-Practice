# FlyRank AI's Polite Scraper

A small, polite web-scraping pipeline for `books.toscrape.com`: it downloads the first three catalogue pages, visits all 60 book pages, turns messy HTML into clean, validated JSON records, survives a broken page without crashing, and ends every run with a short report.

## Target Classification (Stage 0)

- **Site:** `https://books.toscrape.com/` — a well-known public practice target for web scraping.
- **Scope:** the first 3 catalogue pages (20 books each = 60 book detail pages), discovered by following the site's own "next" link — never by hardcoding URLs.
- **Fields per book:** title, product page URL, price (raw text and parsed GBP number), availability, rating, description (may be absent), the catalogue page that listed the book, and when the page was fetched.
- **Robots.txt:** the site ships no `robots.txt`, and these data are not sensitive — appropriate for this practice.
- **Reminder:** this code will not be reused on another site without checking that site's rules and terms first.

## Install

```bash
python -m pip install -r requirements.txt
```

## Run

```bash
python src/main.py
```

The first run downloads and caches every page (3 catalogue pages + 60 book pages), spaced at least 0.5 s apart. Later runs read the cache and hit the site only for pages it does not already have. Every run ends with three files:

- `output/books.json` — the validated records
- `output/errors.json` — records that failed validation, with reasons (empty on a clean run)
- `output/run-report.json` — honest numbers about the run

Optional: `python src/main.py --test-broken-book` adds one made-up book URL (a real 404) to prove that one broken page is logged and skipped without losing the good records.

## Polite identity

Every request uses a user-agent that names the bot and links the repo, so a site owner reading their logs can find out exactly who is asking:

```
FlyRankInternshipA9/1.0 (+https://github.com/AnelkaCH/2026Project-FlyRank-AI-Polite-Scraper-Practice)
```

## Record schema

Each record in `output/books.json` is validated by a Pydantic model (`src/models.py`). A record that fails validation never reaches `books.json`; it lands in `errors.json` with the reason.

| Field | Type | Required |
|---|---|---|
| `title` | string | yes |
| `product_url` | string (`https://…`) — the canonical identity of the book | yes |
| `price_text` | string — the raw text as scraped, e.g. `£51.77` | yes |
| `price_gbp` | number (float) — parsed from `price_text`, e.g. `51.77` | yes |
| `availability_text` | string | yes |
| `rating_text` | string, e.g. `Three` | yes |
| `description` | string or `null` — some books have none, and the site's text is stored verbatim | no |
| `source_page` | string (`https://…`) — which catalogue page listed the book | yes |
| `fetched_at` | string — UTC timestamp in ISO 8601, e.g. `2026-08-08T14:12:21Z` | yes |

## Politeness rules

- **Honest user-agent** naming the bot and linking the repo (see above).
- **Delay:** at least 0.5 s between real requests; 1 s before a retry. Cached pages never leave the computer and need no delay.
- **Timeout:** every request gives up after 10 s — it never waits forever.
- **Status check:** only HTTP 200 is treated as "here is your page"; anything else is a failed fetch, not HTML to parse.
- **Retry once** on timeout, connection error, or 5xx. Never on 404 (the page does not exist — asking again will not create it) or 403 (the site said no — asking again is how a polite robot becomes a pest).
- **Cache-first:** every downloaded page is saved to `cache/` and reused, so each page is requested from the site only once.

## One honest limitation

`books.toscrape.com` is a demo site — the site itself warns that its prices and ratings are randomly assigned, so `price_gbp` and `rating_text` carry no real-world meaning. The parsers are also tied to the site's current HTML template; a redesign of the pages would break the selectors in `src/main.py`.

## Proof it runs

A real run-report from a `--test-broken-book` run (all 63 real pages served from cache — zero requests to the site — plus one deliberately added made-up book URL that 404s). The 60 good records survive, the bad one is logged and skipped, and the report says so:

```json
{
  "start_time": "2026-08-08T14:14:02Z",
  "duration_seconds": 2.261,
  "pages_fetched": 0,
  "cache_hits": 63,
  "valid_records": 60,
  "invalid_records": 0,
  "failed_pages": 1,
  "failed_page_urls": [
    "https://books.toscrape.com/catalogue/not-a-real-book_999999/index.html"
  ]
}
```

## Why no browser?

This assignment needed no browser because every fact we collect already exists in the raw HTML the server sends — rendering that HTML in a browser would only add cost, latency, and fragility without adding a single bit of information.

## Ethics

Use an official API when one exists; never bypass logins, paywalls, or blocks; and collect only what you need. This project scrapes public, non-sensitive data from a dedicated practice site, politely and at low volume.
