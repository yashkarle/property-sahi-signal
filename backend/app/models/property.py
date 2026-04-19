import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base

PropertyTypeEnum = Enum(
    "apartment", "duplex", "house", "own_door_apartment",
    name="property_type_enum",
)
HeatingTypeEnum = Enum(
    "gas", "oil", "electric_storage", "heat_pump", "unknown",
    name="heating_type_enum",
)
SellerStatusEnum = Enum(
    "chain_free", "turnkey", "renting", "living", "unknown",
    name="seller_status_enum",
)
SourceEnum = Enum("daft", "myhome", name="source_enum")


class Property(Base):
    __tablename__ = "properties"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(SourceEnum, nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(1024), unique=True, nullable=False)

    title: Mapped[str | None] = mapped_column(String(512))
    address: Mapped[str | None] = mapped_column(String(512))
    eircode: Mapped[str | None] = mapped_column(String(16), index=True)
    latitude: Mapped[float | None] = mapped_column(Numeric(10, 7))
    longitude: Mapped[float | None] = mapped_column(Numeric(10, 7))
    dublin_district: Mapped[str | None] = mapped_column(String(8), index=True)

    price: Mapped[int | None] = mapped_column(Integer, index=True)
    price_history: Mapped[dict | None] = mapped_column(JSONB)

    bedrooms: Mapped[int | None] = mapped_column(Integer, index=True)
    bathrooms: Mapped[int | None] = mapped_column(Integer, index=True)

    # Carpet floor area ONLY (excluding hallways/common areas — key differentiator)
    carpet_area_sqm: Mapped[int | None] = mapped_column(Integer, index=True)

    property_type: Mapped[str | None] = mapped_column(PropertyTypeEnum, index=True)
    ber_rating: Mapped[str | None] = mapped_column(String(4), index=True)
    heating_type: Mapped[str | None] = mapped_column(HeatingTypeEnum, index=True)
    year_built: Mapped[int | None] = mapped_column(Integer, index=True)
    management_fee_eur: Mapped[int | None] = mapped_column(Integer)

    is_chain_free: Mapped[bool | None] = mapped_column(Boolean, index=True)
    seller_status: Mapped[str | None] = mapped_column(SellerStatusEnum, index=True)
    is_south_facing: Mapped[bool | None] = mapped_column(Boolean)
    is_htb_eligible: Mapped[bool | None] = mapped_column(Boolean, index=True)

    days_on_market: Mapped[int | None] = mapped_column(Integer, index=True)
    estate_agent: Mapped[str | None] = mapped_column(String(256), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    features_list: Mapped[list | None] = mapped_column(JSONB)

    # Flags for missing data — drives viewing prep rule engine
    missing_data_flags: Mapped[list | None] = mapped_column(JSONB)

    # OpenSearch document reference
    embedding_id: Mapped[str | None] = mapped_column(String(256))

    last_scraped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    # Relationships
    neighbourhood_score: Mapped["NeighbourhoodScore | None"] = relationship(  # noqa: F821
        "NeighbourhoodScore", back_populates="property", uselist=False
    )
    bid_sessions: Mapped[list["BidSession"]] = relationship(  # noqa: F821
        "BidSession", back_populates="property"
    )
    price_model_results: Mapped[list["PriceModelResult"]] = relationship(  # noqa: F821
        "PriceModelResult", back_populates="property"
    )

    @property
    def is_celtic_tiger_era(self) -> bool:
        return self.year_built is not None and 2000 <= self.year_built <= 2008

    @property
    def price_per_sqm(self) -> float | None:
        if self.price and self.carpet_area_sqm:
            return self.price / self.carpet_area_sqm
        return None
