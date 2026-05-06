import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base

BidSessionStatusEnum = Enum(
    "active", "won", "lost", "withdrawn",
    name="bid_session_status_enum",
)
BidSubmitterEnum = Enum("user", "other_buyer", name="bid_submitter_enum")


class BidSession(Base):
    __tablename__ = "bid_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("properties.id", ondelete="CASCADE"),
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    status: Mapped[str] = mapped_column(BidSessionStatusEnum, default="active", index=True)
    user_max_budget: Mapped[int | None] = mapped_column(Integer)
    user_aip: Mapped[int | None] = mapped_column(Integer)
    user_savings: Mapped[int | None] = mapped_column(Integer)
    actual_sale_price: Mapped[int | None] = mapped_column(Integer)
    strategy_advice: Mapped[str | None] = mapped_column(Text)

    property: Mapped["Property"] = relationship(  # noqa: F821
        "Property", back_populates="bid_sessions"
    )
    entries: Mapped[list["BidEntry"]] = relationship(
        "BidEntry", back_populates="session", order_by="BidEntry.submitted_at"
    )


class BidEntry(Base):
    """Append-only bid log — never update, only insert."""

    __tablename__ = "bid_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bid_sessions.id", ondelete="CASCADE"),
        index=True,
    )
    bid_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    submitted_by: Mapped[str] = mapped_column(BidSubmitterEnum, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    notes: Mapped[str | None] = mapped_column(Text)
    is_winning: Mapped[bool] = mapped_column(Boolean, default=False)

    session: Mapped[BidSession] = relationship("BidSession", back_populates="entries")
