import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class PriceModelResult(Base):
    """Full BuyerEdge-style output from the pricing pipeline (dhub PyMC skill)."""

    __tablename__ = "price_model_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("properties.id", ondelete="CASCADE"),
        index=True,
    )
    run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)

    # Comparable selection metadata
    n_comparables: Mapped[int | None] = mapped_column(Integer)
    geographic_radius_m: Mapped[int | None] = mapped_column(Integer)
    temporal_window_months: Mapped[int | None] = mapped_column(Integer)
    comparables_used: Mapped[list | None] = mapped_column(JSONB)

    # Distribution (€, time-adjusted, winsorised)
    size_adjusted_fair_value: Mapped[int | None] = mapped_column(Integer)
    p25_estimate: Mapped[int | None] = mapped_column(Integer)
    p50_estimate: Mapped[int | None] = mapped_column(Integer)
    p75_estimate: Mapped[int | None] = mapped_column(Integer)
    iqr: Mapped[int | None] = mapped_column(Integer)

    # Confidence
    confidence_raw: Mapped[float | None] = mapped_column(Numeric(4, 3))
    caf: Mapped[float | None] = mapped_column(Numeric(4, 3))
    confidence_final: Mapped[float | None] = mapped_column(Numeric(4, 3))

    # Market signals
    active_supply_count: Mapped[int | None] = mapped_column(Integer)
    months_supply: Mapped[float | None] = mapped_column(Numeric(4, 1))
    seller_leverage_score: Mapped[float | None] = mapped_column(Numeric(4, 1))
    sealed_bid_probability: Mapped[float | None] = mapped_column(Numeric(4, 3))
    over_asking_probability: Mapped[float | None] = mapped_column(Numeric(4, 3))

    # Offer band (€, rounded to nearest €2,500)
    offer_entry: Mapped[int | None] = mapped_column(Integer)
    offer_sealed: Mapped[int | None] = mapped_column(Integer)
    offer_ceiling: Mapped[int | None] = mapped_column(Integer)

    # Subjective adjustments applied (our differentiator)
    subjective_inputs: Mapped[dict | None] = mapped_column(JSONB)
    subjective_adjustment_factor: Mapped[float | None] = mapped_column(Numeric(5, 4))

    # Buyer constraint (from financing simulator)
    buyer_ceiling: Mapped[int | None] = mapped_column(Integer)

    # Model metadata
    model_params: Mapped[dict | None] = mapped_column(JSONB)
    s3_cache_key: Mapped[str | None] = mapped_column(String(256))

    property: Mapped["Property"] = relationship(  # noqa: F821
        "Property", back_populates="price_model_results"
    )
