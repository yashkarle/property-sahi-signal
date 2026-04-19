import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class NeighbourhoodScore(Base):
    __tablename__ = "neighbourhood_scores"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("properties.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )

    # 8 dimensions scored 0-10 via Overpass API (OSM)
    safety_score: Mapped[float | None] = mapped_column(Numeric(3, 1))       # Garda ≤2km
    amenities_score: Mapped[float | None] = mapped_column(Numeric(3, 1))    # Shops/pharmacy ≤1km
    connectivity_score: Mapped[float | None] = mapped_column(Numeric(3, 1)) # Luas ≤800m, bus ≤400m
    schools_score: Mapped[float | None] = mapped_column(Numeric(3, 1))      # Primary/secondary ≤1km
    parks_score: Mapped[float | None] = mapped_column(Numeric(3, 1))        # Green ≤500m
    cafes_score: Mapped[float | None] = mapped_column(Numeric(3, 1))        # Cafes ≤500m
    supermarkets_score: Mapped[float | None] = mapped_column(Numeric(3, 1)) # Lidl/Aldi/Tesco ≤1km
    m50_n11_score: Mapped[float | None] = mapped_column(Numeric(3, 1))      # Motorway jct ≤3km

    overall_score: Mapped[float | None] = mapped_column(Numeric(3, 1))
    commute_dundrum_min: Mapped[int | None] = mapped_column(Numeric(5, 1))

    data_sources: Mapped[dict | None] = mapped_column(JSONB)
    overpass_raw: Mapped[dict | None] = mapped_column(JSONB)

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    property: Mapped["Property"] = relationship(  # noqa: F821
        "Property", back_populates="neighbourhood_score"
    )

    WEIGHTS = {
        "safety": 0.10,
        "amenities": 0.15,
        "connectivity": 0.20,
        "schools": 0.15,
        "parks": 0.10,
        "cafes": 0.10,
        "supermarkets": 0.10,
        "m50_n11": 0.10,
    }

    def compute_overall(self) -> float:
        scores = {
            "safety": self.safety_score or 0,
            "amenities": self.amenities_score or 0,
            "connectivity": self.connectivity_score or 0,
            "schools": self.schools_score or 0,
            "parks": self.parks_score or 0,
            "cafes": self.cafes_score or 0,
            "supermarkets": self.supermarkets_score or 0,
            "m50_n11": self.m50_n11_score or 0,
        }
        return sum(scores[k] * w for k, w in self.WEIGHTS.items())
