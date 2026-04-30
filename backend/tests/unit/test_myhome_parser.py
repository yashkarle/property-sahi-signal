from pathlib import Path
from ingestion.scrapers.myhome_scraper import parse_myhome_listing_html

FIXTURE = Path(__file__).parent.parent / "fixtures" / "myhome_sample.html"
URL = "https://www.myhome.ie/residential/brochure/stocking-wood-hall/12345"


def test_parse_myhome_listing_html_happy_path() -> None:
    listing = parse_myhome_listing_html(FIXTURE.read_text(), URL)
    assert listing is not None
    assert listing.price == 380000
    assert listing.bedrooms == 3
    assert listing.bathrooms == 2
    assert listing.carpet_area_sqm == 110
    assert listing.ber_rating == "B1"
    assert listing.source_id == "12345"
    assert listing.source == "myhome"
    assert listing.url == URL


def test_parse_myhome_listing_html_returns_none_on_missing_required_fields() -> None:
    result = parse_myhome_listing_html("<html><body></body></html>", URL)
    assert result is None
