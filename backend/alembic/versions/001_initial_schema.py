"""Initial schema — all tables.

Revision ID: 001
Revises:
Create Date: 2026-04-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enums
    op.execute("CREATE TYPE source_enum AS ENUM ('daft', 'myhome')")
    op.execute("CREATE TYPE property_type_enum AS ENUM ('apartment', 'duplex', 'house', 'own_door_apartment')")
    op.execute("CREATE TYPE heating_type_enum AS ENUM ('gas', 'oil', 'electric_storage', 'heat_pump', 'unknown')")
    op.execute("CREATE TYPE seller_status_enum AS ENUM ('chain_free', 'turnkey', 'renting', 'living', 'unknown')")
    op.execute("CREATE TYPE bid_session_status_enum AS ENUM ('active', 'won', 'lost', 'withdrawn')")
    op.execute("CREATE TYPE bid_submitter_enum AS ENUM ('user', 'other_buyer')")
    op.execute("CREATE TYPE professional_type_enum AS ENUM ('solicitor', 'surveyor')")
    op.execute("CREATE TYPE professional_source_enum AS ENUM ('scsi', 'engineers_ireland')")

    # properties
    op.create_table(
        "properties",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source", sa.Enum("daft", "myhome", name="source_enum"), nullable=False),
        sa.Column("source_id", sa.String(128), nullable=False),
        sa.Column("url", sa.String(1024), unique=True, nullable=False),
        sa.Column("title", sa.String(512)),
        sa.Column("address", sa.String(512)),
        sa.Column("eircode", sa.String(16)),
        sa.Column("latitude", sa.Numeric(10, 7)),
        sa.Column("longitude", sa.Numeric(10, 7)),
        sa.Column("dublin_district", sa.String(8)),
        sa.Column("price", sa.Integer),
        sa.Column("price_history", postgresql.JSONB),
        sa.Column("bedrooms", sa.Integer),
        sa.Column("bathrooms", sa.Integer),
        sa.Column("carpet_area_sqm", sa.Integer),
        sa.Column("property_type", sa.Enum("apartment", "duplex", "house", "own_door_apartment", name="property_type_enum")),
        sa.Column("ber_rating", sa.String(4)),
        sa.Column("heating_type", sa.Enum("gas", "oil", "electric_storage", "heat_pump", "unknown", name="heating_type_enum")),
        sa.Column("year_built", sa.Integer),
        sa.Column("management_fee_eur", sa.Integer),
        sa.Column("is_chain_free", sa.Boolean),
        sa.Column("seller_status", sa.Enum("chain_free", "turnkey", "renting", "living", "unknown", name="seller_status_enum")),
        sa.Column("is_south_facing", sa.Boolean),
        sa.Column("is_htb_eligible", sa.Boolean),
        sa.Column("days_on_market", sa.Integer),
        sa.Column("estate_agent", sa.String(256)),
        sa.Column("description", sa.Text),
        sa.Column("features_list", postgresql.JSONB),
        sa.Column("missing_data_flags", postgresql.JSONB),
        sa.Column("embedding_id", sa.String(256)),
        sa.Column("last_scraped_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
    )
    op.create_index("ix_properties_source", "properties", ["source"])
    op.create_index("ix_properties_source_id", "properties", ["source_id"])
    op.create_index("ix_properties_eircode", "properties", ["eircode"])
    op.create_index("ix_properties_dublin_district", "properties", ["dublin_district"])
    op.create_index("ix_properties_price", "properties", ["price"])
    op.create_index("ix_properties_is_active", "properties", ["is_active"])

    # ppr_sales
    op.create_table(
        "ppr_sales",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("address", sa.String(512), nullable=False),
        sa.Column("eircode", sa.String(16)),
        sa.Column("county", sa.String(64)),
        sa.Column("date_of_sale", sa.Date, nullable=False),
        sa.Column("price_eur", sa.Integer, nullable=False),
        sa.Column("not_full_market_price", sa.Boolean, default=False),
        sa.Column("vat_exclusive", sa.Boolean, default=False),
        sa.Column("property_description", sa.String(256)),
        sa.Column("floor_area_sqm", sa.Integer),
        sa.Column("price_per_sqm", sa.Numeric(10, 2)),
        sa.Column("bedrooms", sa.Integer),
        sa.Column("property_type", sa.String(64)),
        sa.Column("latitude", sa.Numeric(10, 7)),
        sa.Column("longitude", sa.Numeric(10, 7)),
        sa.Column("dublin_district", sa.String(8)),
        sa.Column("source_file", sa.String(64)),
        sa.Column("scraped_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("matched_property_id", postgresql.UUID(as_uuid=True)),
    )
    op.create_index("ix_ppr_sales_eircode", "ppr_sales", ["eircode"])
    op.create_index("ix_ppr_sales_county", "ppr_sales", ["county"])
    op.create_index("ix_ppr_sales_date_of_sale", "ppr_sales", ["date_of_sale"])
    op.create_index("ix_ppr_sales_dublin_district", "ppr_sales", ["dublin_district"])

    # neighbourhood_scores
    op.create_table(
        "neighbourhood_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("property_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("properties.id", ondelete="CASCADE"), unique=True),
        sa.Column("safety_score", sa.Numeric(3, 1)),
        sa.Column("amenities_score", sa.Numeric(3, 1)),
        sa.Column("connectivity_score", sa.Numeric(3, 1)),
        sa.Column("schools_score", sa.Numeric(3, 1)),
        sa.Column("parks_score", sa.Numeric(3, 1)),
        sa.Column("cafes_score", sa.Numeric(3, 1)),
        sa.Column("supermarkets_score", sa.Numeric(3, 1)),
        sa.Column("m50_n11_score", sa.Numeric(3, 1)),
        sa.Column("overall_score", sa.Numeric(3, 1)),
        sa.Column("commute_dundrum_min", sa.Numeric(5, 1)),
        sa.Column("data_sources", postgresql.JSONB),
        sa.Column("overpass_raw", postgresql.JSONB),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # bid_sessions
    op.create_table(
        "bid_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("property_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("properties.id", ondelete="CASCADE")),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("status", sa.Enum("active", "won", "lost", "withdrawn", name="bid_session_status_enum"), default="active"),
        sa.Column("user_max_budget", sa.Integer),
        sa.Column("strategy_advice", sa.Text),
    )

    # bid_entries
    op.create_table(
        "bid_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("bid_sessions.id", ondelete="CASCADE")),
        sa.Column("bid_amount", sa.Integer, nullable=False),
        sa.Column("submitted_by", sa.Enum("user", "other_buyer", name="bid_submitter_enum"), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("notes", sa.Text),
        sa.Column("is_winning", sa.Boolean, default=False),
    )

    # professionals
    op.create_table(
        "professionals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("professional_type", sa.Enum("solicitor", "surveyor", name="professional_type_enum"), nullable=False),
        sa.Column("source", sa.Enum("scsi", "engineers_ireland", name="professional_source_enum"), nullable=False),
        sa.Column("name", sa.String(256)),
        sa.Column("firm_name", sa.String(256)),
        sa.Column("address", sa.String(512)),
        sa.Column("eircode", sa.String(16)),
        sa.Column("latitude", sa.Numeric(10, 7)),
        sa.Column("longitude", sa.Numeric(10, 7)),
        sa.Column("phone", sa.String(32)),
        sa.Column("email", sa.String(256)),
        sa.Column("website", sa.String(512)),
        sa.Column("specialties", postgresql.JSONB),
        sa.Column("last_verified_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # price_model_results
    op.create_table(
        "price_model_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("property_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("properties.id", ondelete="CASCADE")),
        sa.Column("run_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("status", sa.String(16), default="pending"),
        sa.Column("n_comparables", sa.Integer),
        sa.Column("geographic_radius_m", sa.Integer),
        sa.Column("temporal_window_months", sa.Integer),
        sa.Column("comparables_used", postgresql.JSONB),
        sa.Column("size_adjusted_fair_value", sa.Integer),
        sa.Column("p25_estimate", sa.Integer),
        sa.Column("p50_estimate", sa.Integer),
        sa.Column("p75_estimate", sa.Integer),
        sa.Column("iqr", sa.Integer),
        sa.Column("confidence_raw", sa.Numeric(4, 3)),
        sa.Column("caf", sa.Numeric(4, 3)),
        sa.Column("confidence_final", sa.Numeric(4, 3)),
        sa.Column("active_supply_count", sa.Integer),
        sa.Column("months_supply", sa.Numeric(4, 1)),
        sa.Column("seller_leverage_score", sa.Numeric(4, 1)),
        sa.Column("sealed_bid_probability", sa.Numeric(4, 3)),
        sa.Column("over_asking_probability", sa.Numeric(4, 3)),
        sa.Column("offer_entry", sa.Integer),
        sa.Column("offer_sealed", sa.Integer),
        sa.Column("offer_ceiling", sa.Integer),
        sa.Column("subjective_inputs", postgresql.JSONB),
        sa.Column("subjective_adjustment_factor", sa.Numeric(5, 4)),
        sa.Column("buyer_ceiling", sa.Integer),
        sa.Column("model_params", postgresql.JSONB),
        sa.Column("s3_cache_key", sa.String(256)),
    )

    # admin_logs
    op.create_table(
        "admin_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("endpoint", sa.String(256)),
        sa.Column("request_payload", postgresql.JSONB),
        sa.Column("response_summary", postgresql.JSONB),
        sa.Column("bedrock_tokens_in", sa.Integer),
        sa.Column("bedrock_tokens_out", sa.Integer),
        sa.Column("duration_ms", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_admin_logs_event_type", "admin_logs", ["event_type"])
    op.create_index("ix_admin_logs_created_at", "admin_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("admin_logs")
    op.drop_table("price_model_results")
    op.drop_table("professionals")
    op.drop_table("bid_entries")
    op.drop_table("bid_sessions")
    op.drop_table("neighbourhood_scores")
    op.drop_table("ppr_sales")
    op.drop_table("properties")
    op.execute("DROP TYPE IF EXISTS professional_source_enum")
    op.execute("DROP TYPE IF EXISTS professional_type_enum")
    op.execute("DROP TYPE IF EXISTS bid_submitter_enum")
    op.execute("DROP TYPE IF EXISTS bid_session_status_enum")
    op.execute("DROP TYPE IF EXISTS seller_status_enum")
    op.execute("DROP TYPE IF EXISTS heating_type_enum")
    op.execute("DROP TYPE IF EXISTS property_type_enum")
    op.execute("DROP TYPE IF EXISTS source_enum")
