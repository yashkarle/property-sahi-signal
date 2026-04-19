import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class PPRSale(Base):
    """Irish Property Price Register — every residential sale in Ireland."""

    __tablename__ = "ppr_sales"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    address: Mapped[str] = mapped_column(String(512), nullable=False)
    eircode: Mapped[str | None] = mapped_column(String(16), index=True)
    county: Mapped[str | None] = mapped_column(String(64), index=True)
    date_of_sale: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    price_eur: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    not_full_market_price: Mapped[bool] = mapped_column(Boolean, default=False)
    vat_exclusive: Mapped[bool] = mapped_column(Boolean, default=False)
    property_description: Mapped[str | None] = mapped_column(String(256))

    # Enriched fields (matched against active listings or estimated)
    floor_area_sqm: Mapped[int | None] = mapped_column(Integer)
    price_per_sqm: Mapped[float | None] = mapped_column(Numeric(10, 2))
    bedrooms: Mapped[int | None] = mapped_column(Integer)
    property_type: Mapped[str | None] = mapped_column(String(64))

    # Geocoded
    latitude: Mapped[float | None] = mapped_column(Numeric(10, 7))
    longitude: Mapped[float | None] = mapped_column(Numeric(10, 7))
    dublin_district: Mapped[str | None] = mapped_column(String(8), index=True)

    source_file: Mapped[str | None] = mapped_column(String(64))
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Linked to an active property listing (if matched)
    matched_property_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
