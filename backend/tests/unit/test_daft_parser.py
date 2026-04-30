from pathlib import Path
from ingestion.scrapers.daft_scraper import parse_daft_listing_html

FIXTURE = Path(__file__).parent.parent / "fixtures" / "daft_sample.html"
URL = "https://www.daft.ie/for-sale/house-stocking-wood-hall/6519399"


def test_parse_daft_listing_html_happy_path() -> None:
    listing = parse_daft_listing_html(FIXTURE.read_text(), URL)
    assert listing is not None
    assert listing.price == 375000
    assert listing.bedrooms == 3
    assert listing.bathrooms == 2
    assert listing.carpet_area_sqm == 105
    assert listing.ber_rating == "B2"
    assert listing.source_id == "6519399"
    assert listing.source == "daft"
    assert listing.url == URL


def test_parse_daft_listing_html_returns_none_on_missing_required_fields() -> None:
    result = parse_daft_listing_html("<html><body></body></html>", URL)
    assert result is None
