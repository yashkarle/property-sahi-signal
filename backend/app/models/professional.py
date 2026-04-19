import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base

ProfessionalTypeEnum = Enum("solicitor", "surveyor", name="professional_type_enum")
ProfessionalSourceEnum = Enum("scsi", "engineers_ireland", name="professional_source_enum")


class Professional(Base):
    __tablename__ = "professionals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    professional_type: Mapped[str] = mapped_column(ProfessionalTypeEnum, nullable=False, index=True)
    source: Mapped[str] = mapped_column(ProfessionalSourceEnum, nullable=False)

    name: Mapped[str | None] = mapped_column(String(256))
    firm_name: Mapped[str | None] = mapped_column(String(256))
    address: Mapped[str | None] = mapped_column(String(512))
    eircode: Mapped[str | None] = mapped_column(String(16))
    latitude: Mapped[float | None] = mapped_column(Numeric(10, 7))
    longitude: Mapped[float | None] = mapped_column(Numeric(10, 7))

    phone: Mapped[str | None] = mapped_column(String(32))
    email: Mapped[str | None] = mapped_column(String(256))
    website: Mapped[str | None] = mapped_column(String(512))

    specialties: Mapped[list | None] = mapped_column(JSONB)

    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
