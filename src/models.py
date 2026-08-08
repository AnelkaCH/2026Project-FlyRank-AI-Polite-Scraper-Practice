"""Schema for a finished book record, plus the price parser."""
import re

from pydantic import BaseModel, field_validator


class PriceParseError(ValueError):
    pass


def parse_price(price_text: str | None) -> float:
    match = re.search(r"\u00a3?\s*([\d,]+(?:\.\d+)?)", price_text or "")
    if match is None:
        raise PriceParseError(f"could not parse a price from {price_text!r}")
    return float(match.group(1).replace(",", ""))


class BookRecord(BaseModel):
    title: str
    product_url: str
    price_text: str
    price_gbp: float
    availability_text: str
    rating_text: str
    description: str | None = None
    source_page: str
    fetched_at: str

    @field_validator("product_url", "source_page")
    @classmethod
    def _https_only(cls, value: str) -> str:
        if not value.startswith("https://"):
            raise ValueError("must start with https://")
        return value
