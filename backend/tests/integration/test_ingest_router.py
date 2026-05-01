from pathlib import Path

import pytest
from httpx import AsyncClient

DAFT_HTML = (Path(__file__).parent.parent / "fixtures" / "daft_sample.html").read_text()
DAFT_URL = "https://www.daft.ie/for-sale/house-stocking-wood-hall-rathfarnham-dublin-16/6519399"
API_KEY = "change-me-in-production"


class _FakeBrowser:
    async def close(self) -> None: ...


@pytest.fixture(autouse=True)
def _mock_browser(monkeypatch) -> None:
    async def _get_browser():
        return _FakeBrowser()
    monkeypatch.setattr("ingestion.scrapers.base_scraper.get_browser", _get_browser)


async def test_ingest_url_happy_path(client: AsyncClient, monkeypatch) -> None:
    async def _mock_html(url, browser):
        return DAFT_HTML
    monkeypatch.setattr("ingestion.scrapers.base_scraper.get_page_html", _mock_html)

    resp = await client.post(
        "/api/v1/ingest/url",
        json={"url": DAFT_URL},
        headers={"X-API-Key": API_KEY},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert data["price"] == 375000
    assert data["bedrooms"] == 3
    assert data["bathrooms"] == 2


async def test_ingest_same_url_is_idempotent(client: AsyncClient, monkeypatch) -> None:
    async def _mock_html(url, browser):
        return DAFT_HTML
    monkeypatch.setattr("ingestion.scrapers.base_scraper.get_page_html", _mock_html)

    resp1 = await client.post(
        "/api/v1/ingest/url", json={"url": DAFT_URL}, headers={"X-API-Key": API_KEY}
    )
    resp2 = await client.post(
        "/api/v1/ingest/url", json={"url": DAFT_URL}, headers={"X-API-Key": API_KEY}
    )
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp1.json()["id"] == resp2.json()["id"]


async def test_ingest_unsupported_portal(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/ingest/url",
        json={"url": "https://www.mulleryogara.ie/property/123"},
        headers={"X-API-Key": API_KEY},
    )
    assert resp.status_code == 400
    assert "Unsupported portal" in resp.json()["detail"]


async def test_ingest_portal_unreachable(client: AsyncClient, monkeypatch) -> None:
    async def _mock_none(url, browser):
        return None
    monkeypatch.setattr("ingestion.scrapers.base_scraper.get_page_html", _mock_none)

    resp = await client.post(
        "/api/v1/ingest/url", json={"url": DAFT_URL}, headers={"X-API-Key": API_KEY}
    )
    assert resp.status_code == 502


async def test_ingest_parse_failure(client: AsyncClient, monkeypatch) -> None:
    async def _mock_empty(url, browser):
        return "<html><body></body></html>"
    monkeypatch.setattr("ingestion.scrapers.base_scraper.get_page_html", _mock_empty)

    resp = await client.post(
        "/api/v1/ingest/url", json={"url": DAFT_URL}, headers={"X-API-Key": API_KEY}
    )
    assert resp.status_code == 422
    assert "Could not parse" in resp.json()["detail"]
