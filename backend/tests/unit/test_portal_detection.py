import pytest
from app.services.url_ingest_service import detect_portal


@pytest.mark.parametrize("url,expected", [
    ("https://www.daft.ie/for-sale/house/6519399", "daft.ie"),
    ("https://daft.ie/for-sale/apartment/123", "daft.ie"),
    ("https://www.myhome.ie/residential/brochure/house/12345", "myhome.ie"),
    ("https://myhome.ie/residential/brochure/house/12345", "myhome.ie"),
    ("https://www.mulleryogara.ie/property/123", None),
    ("https://www.google.com", None),
    ("not-a-url", None),
    ("", None),
])
def test_detect_portal(url: str, expected: str | None) -> None:
    assert detect_portal(url) == expected
