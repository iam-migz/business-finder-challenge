from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, selectinload

from app.models import ABSDownload, ABSRelease, ABSTable, ABSTableRow
from app.services.abs_scraper import ScrapedABSRelease


def persist_abs_releases(db: Session, releases: list[ScrapedABSRelease]) -> int:
    stored = 0
    for scraped_release in releases:
        existing = db.get(ABSRelease, scraped_release.slug)
        if existing:
            db.delete(existing)
            db.flush()

        release = ABSRelease(
            slug=scraped_release.slug,
            title=scraped_release.title,
            source_url=scraped_release.source_url,
            description=scraped_release.description,
            reference_period=scraped_release.reference_period,
            released=scraped_release.released,
            release_date_time=scraped_release.release_date_time,
            key_statistics=scraped_release.key_statistics,
            scraped_at=datetime.now(UTC),
        )
        db.add(release)
        db.flush()

        for table_data in scraped_release.tables:
            table = ABSTable(
                release_slug=release.slug,
                table_index=table_data["table_index"],
                title=table_data["title"],
                headers=table_data["headers"],
                row_count=len(table_data["rows"]),
            )
            db.add(table)
            db.flush()

            for row_data in table_data["rows"]:
                db.add(
                    ABSTableRow(
                        table_id=table.id,
                        row_index=row_data["row_index"],
                        label=row_data["label"],
                        values=row_data["values"],
                    )
                )

        for download_data in scraped_release.downloads:
            db.add(
                ABSDownload(
                    release_slug=release.slug,
                    title=download_data["title"],
                    href=download_data["href"],
                    file_type=download_data["file_type"],
                    size_label=download_data["size_label"],
                )
            )

        stored += 1

    return stored


def abs_release_summary(db: Session) -> dict[str, Any]:
    releases = db.scalars(
        select(ABSRelease).order_by(desc(ABSRelease.scraped_at))
    ).all()
    return {
        "count": len(releases),
        "table_count": db.scalar(select(func.count()).select_from(ABSTable)) or 0,
        "row_count": db.scalar(select(func.count()).select_from(ABSTableRow)) or 0,
        "download_count": db.scalar(select(func.count()).select_from(ABSDownload)) or 0,
        "data": [_release_to_dict(release) for release in releases],
    }


def abs_release_detail(db: Session, slug: str) -> dict[str, Any] | None:
    release = db.scalars(
        select(ABSRelease)
        .where(ABSRelease.slug == slug)
        .options(
            selectinload(ABSRelease.tables).selectinload(ABSTable.rows),
            selectinload(ABSRelease.downloads),
        )
    ).first()
    if not release:
        return None

    return {
        **_release_to_dict(release),
        "tables": [
            {
                "id": table.id,
                "table_index": table.table_index,
                "title": table.title,
                "headers": table.headers,
                "row_count": table.row_count,
                "rows": [
                    {
                        "row_index": row.row_index,
                        "label": row.label,
                        "values": row.values,
                    }
                    for row in sorted(table.rows, key=lambda item: item.row_index)
                ],
            }
            for table in sorted(release.tables, key=lambda item: item.table_index)
        ],
        "downloads": [
            {
                "title": download.title,
                "href": download.href,
                "file_type": download.file_type,
                "size_label": download.size_label,
            }
            for download in release.downloads
        ],
    }


def _release_to_dict(release: ABSRelease) -> dict[str, Any]:
    return {
        "slug": release.slug,
        "title": release.title,
        "source_url": release.source_url,
        "description": release.description,
        "reference_period": release.reference_period,
        "released": release.released,
        "release_date_time": release.release_date_time,
        "key_statistics": release.key_statistics,
        "scraped_at": release.scraped_at.isoformat() if release.scraped_at else None,
        "table_count": len(release.tables),
        "download_count": len(release.downloads),
    }
