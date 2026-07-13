"""PostgreSQL table models (mirrors legacy SQLite schema + SaaS tables)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    password_hash: Mapped[str | None] = mapped_column(Text)
    google_sub: Mapped[str | None] = mapped_column(Text, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    settings: Mapped[UserSettings | None] = relationship(back_populates="user")
    profile: Mapped[UserProfile | None] = relationship(back_populates="user")
    trips: Mapped[list[Trip]] = relationship(back_populates="user")


class UserSettings(Base):
    __tablename__ = "user_settings"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    llm_api_key_enc: Mapped[str | None] = mapped_column(Text)
    llm_base_url: Mapped[str | None] = mapped_column(Text)
    llm_model: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped[User] = relationship(back_populates="settings")


class Trip(Base):
    __tablename__ = "trips"
    __table_args__ = (Index("idx_trips_user_updated", "user_id", "updated_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    city: Mapped[str] = mapped_column(Text, nullable=False)
    dates: Mapped[str] = mapped_column(Text, nullable=False)
    origin_city: Mapped[str] = mapped_column(Text, nullable=False)
    user_query: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped[User] = relationship(back_populates="trips")
    preferences: Mapped[TripPreferences | None] = relationship(back_populates="trip")
    itinerary_versions: Mapped[list[ItineraryVersion]] = relationship(back_populates="trip")


class TripPreferences(Base):
    __tablename__ = "trip_preferences"

    trip_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("trips.id", ondelete="CASCADE"), primary_key=True
    )
    preferences_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    trip: Mapped[Trip] = relationship(back_populates="preferences")


class UserProfile(Base):
    __tablename__ = "user_profile"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    preferences_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped[User] = relationship(back_populates="profile")


class ItineraryVersion(Base):
    __tablename__ = "itinerary_versions"
    __table_args__ = (UniqueConstraint("trip_id", "version", name="uq_itinerary_trip_version"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trip_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    program_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    trip: Mapped[Trip] = relationship(back_populates="itinerary_versions")


class ToolRun(Base):
    __tablename__ = "tool_runs"
    __table_args__ = (Index("idx_tool_runs_trip", "trip_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trip_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False
    )
    itinerary_version_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("itinerary_versions.id", ondelete="SET NULL")
    )
    tool_name: Mapped[str] = mapped_column(Text, nullable=False)
    args_json: Mapped[str | None] = mapped_column(Text)
    provider: Mapped[str | None] = mapped_column(Text)
    live_data: Mapped[bool | None] = mapped_column(Boolean)
    results_count: Mapped[int | None] = mapped_column(Integer)
    raw_results_count: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AgentRun(Base):
    __tablename__ = "agent_runs"
    __table_args__ = (Index("idx_agent_runs_trip", "trip_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trip_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[str] = mapped_column(Text, nullable=False)
    rebuild_scope: Mapped[str] = mapped_column(Text, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    total_tokens: Mapped[int | None] = mapped_column(Integer)
    total_cost_usd: Mapped[float | None] = mapped_column(Float)
    node_timings_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProgramItemFeedback(Base):
    __tablename__ = "program_item_feedback"
    __table_args__ = (
        UniqueConstraint("trip_id", "section", "item_key", name="uq_program_feedback_item"),
        Index("idx_program_feedback_trip", "trip_id"),
        CheckConstraint("vote IN (1, -1)", name="ck_program_feedback_vote"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trip_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False
    )
    itinerary_version_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("itinerary_versions.id", ondelete="SET NULL")
    )
    section: Mapped[str] = mapped_column(Text, nullable=False)
    item_index: Mapped[int] = mapped_column(Integer, nullable=False)
    item_key: Mapped[str] = mapped_column(Text, nullable=False)
    vote: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SectionArtifact(Base):
    __tablename__ = "section_artifacts"

    trip_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("trips.id", ondelete="CASCADE"), primary_key=True
    )
    section: Mapped[str] = mapped_column(Text, primary_key=True)
    digest: Mapped[str | None] = mapped_column(Text)
    payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class GraphRun(Base):
    """Async graph job status (replaces in-memory RunManager)."""

    __tablename__ = "graph_runs"
    __table_args__ = (
        Index("idx_graph_runs_trip_status", "trip_id", "status"),
        Index("idx_graph_runs_user", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    trip_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False
    )
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="queued")
    error: Mapped[str | None] = mapped_column(Text)
    version_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("itinerary_versions.id", ondelete="SET NULL")
    )
    graph_run_id: Mapped[str | None] = mapped_column(Text)
    city_fact_status: Mapped[str] = mapped_column(Text, nullable=False, server_default="idle")
    worker_id: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PoiFact(Base):
    """Глобальный кэш туристической справки по POI (ключ — QID / osm_* / search hash)."""

    __tablename__ = "poi_facts"
    __table_args__ = (Index("idx_poi_facts_status", "status"),)

    cache_key: Mapped[str] = mapped_column(Text, primary_key=True)
    poi_name: Mapped[str] = mapped_column(Text, nullable=False)
    city: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")
    text: Mapped[str | None] = mapped_column(Text)
    source_kind: Mapped[str | None] = mapped_column(Text)
    used_llm: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CityPack(Base):
    """Каталог городских POI-паков (файлы на диске + статус prepare)."""

    __tablename__ = "city_packs"

    slug: Mapped[str] = mapped_column(Text, primary_key=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    federal_district: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="queued")
    poi_count: Mapped[int | None] = mapped_column(Integer)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    prepared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("idx_audit_events_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    ip: Mapped[str | None] = mapped_column(Text)
    user_agent: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class UsageEvent(Base):
    __tablename__ = "usage_events"
    __table_args__ = (Index("idx_usage_events_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    trip_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("trips.id", ondelete="SET NULL")
    )
    graph_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("graph_runs.id", ondelete="SET NULL")
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    total_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
