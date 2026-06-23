from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ScrapeRun(Base):
    __tablename__ = "scrape_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), default="running", nullable=False)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    days: Mapped[int] = mapped_column(Integer, nullable=False)
    max_pages_per_category: Mapped[int] = mapped_column(Integer, nullable=False)
    categories_requested: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    listings_scraped: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    listings_stored: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)

    listings: Mapped[list["BusinessListing"]] = relationship(back_populates="last_seen_run")


class BusinessCategory(Base):
    __tablename__ = "business_categories"

    url_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    seed_url: Mapped[str] = mapped_column(String(255), nullable=False)
    industry_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    total_count: Mapped[int | None] = mapped_column(Integer)
    last_scraped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BusinessListing(Base):
    __tablename__ = "business_listings"

    seek_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    url_key: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(String(800), nullable=False)
    business_name: Mapped[str | None] = mapped_column(String(255), index=True)
    client_id: Mapped[int | None] = mapped_column(Integer)
    client_type: Mapped[str | None] = mapped_column(String(64), index=True)
    category: Mapped[str | None] = mapped_column(String(128), index=True)
    category_url_key: Mapped[str | None] = mapped_column(String(128), index=True)
    category_id: Mapped[int | None] = mapped_column(Integer)
    industry: Mapped[str | None] = mapped_column(String(128), index=True)
    industry_url_key: Mapped[str | None] = mapped_column(String(128))
    industry_id: Mapped[int | None] = mapped_column(Integer)
    industry_tag: Mapped[str | None] = mapped_column(String(128), index=True)
    industry_tag_url_key: Mapped[str | None] = mapped_column(String(128))
    location: Mapped[str | None] = mapped_column(String(255), index=True)
    district_id: Mapped[str | None] = mapped_column(String(64))
    district_type: Mapped[str | None] = mapped_column(String(64))
    district_url_key: Mapped[str | None] = mapped_column(String(255))
    area: Mapped[str | None] = mapped_column(String(128))
    region: Mapped[str | None] = mapped_column(String(128), index=True)
    state: Mapped[str | None] = mapped_column(String(128), index=True)
    country: Mapped[str | None] = mapped_column(String(128))
    price_min: Mapped[int | None] = mapped_column(Integer, index=True)
    price_max: Mapped[int | None] = mapped_column(Integer, index=True)
    is_poa: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_negotiable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_sav: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    opportunity_type: Mapped[str | None] = mapped_column(String(64), index=True)
    is_freemium: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    thumbnail_image_file_name: Mapped[str | None] = mapped_column(String(255))
    image_url: Mapped[str | None] = mapped_column(String(800))
    refresh_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    last_seen_run_id: Mapped[int | None] = mapped_column(ForeignKey("scrape_runs.id"))
    source_category_url_key: Mapped[str | None] = mapped_column(String(128))
    source_page: Mapped[int | None] = mapped_column(Integer)
    source_slot: Mapped[str | None] = mapped_column(String(32))
    raw_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    last_seen_run: Mapped[ScrapeRun | None] = relationship(back_populates="listings")


class ABSRelease(Base):
    __tablename__ = "abs_releases"

    slug: Mapped[str] = mapped_column(String(128), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str] = mapped_column(String(800), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    reference_period: Mapped[str | None] = mapped_column(String(128))
    released: Mapped[str | None] = mapped_column(String(64))
    release_date_time: Mapped[str | None] = mapped_column(String(128))
    key_statistics: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    tables: Mapped[list["ABSTable"]] = relationship(
        back_populates="release", cascade="all, delete-orphan"
    )
    downloads: Mapped[list["ABSDownload"]] = relationship(
        back_populates="release", cascade="all, delete-orphan"
    )


class ABSTable(Base):
    __tablename__ = "abs_tables"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    release_slug: Mapped[str] = mapped_column(ForeignKey("abs_releases.slug"), index=True)
    table_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    headers: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    release: Mapped[ABSRelease] = relationship(back_populates="tables")
    rows: Mapped[list["ABSTableRow"]] = relationship(
        back_populates="table", cascade="all, delete-orphan"
    )


class ABSTableRow(Base):
    __tablename__ = "abs_table_rows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    table_id: Mapped[int] = mapped_column(ForeignKey("abs_tables.id"), index=True)
    row_index: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    values: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    table: Mapped[ABSTable] = relationship(back_populates="rows")


class ABSDownload(Base):
    __tablename__ = "abs_downloads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    release_slug: Mapped[str] = mapped_column(ForeignKey("abs_releases.slug"), index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    href: Mapped[str] = mapped_column(String(800), nullable=False)
    file_type: Mapped[str | None] = mapped_column(String(32))
    size_label: Mapped[str | None] = mapped_column(String(64))

    release: Mapped[ABSRelease] = relationship(back_populates="downloads")
