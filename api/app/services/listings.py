from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import asc, case, desc, func, or_, select
from sqlalchemy.orm import Session

from app.models import BusinessCategory, BusinessListing, ScrapeRun
from app.services.scraper import ScrapeResult, ScrapedListing


def persist_scrape_result(
    db: Session,
    result: ScrapeResult,
    run: ScrapeRun,
) -> int:
    now = datetime.now(UTC)

    for category in result.categories:
        db.merge(
            BusinessCategory(
                url_key=category.url_key,
                name=category.name,
                seed_url=category.seed_url,
                industry_ids=category.industry_ids,
                total_count=category.total_count,
                last_scraped_at=now,
            )
        )

    stored = 0
    for scraped_listing in result.listings:
        existing = db.get(BusinessListing, scraped_listing.seek_id)
        if existing:
            _update_listing(existing, scraped_listing, run.id, now)
        else:
            db.add(_new_listing(scraped_listing, run.id, now))
        stored += 1

    return stored


def list_categories(db: Session) -> list[dict[str, Any]]:
    rows = db.execute(
        select(
            BusinessCategory,
            func.count(BusinessListing.seek_id).label("stored_listings"),
        )
        .outerjoin(
            BusinessListing,
            BusinessListing.category_url_key == BusinessCategory.url_key,
        )
        .group_by(BusinessCategory.url_key)
        .order_by(BusinessCategory.name)
    ).all()

    return [
        {
            "name": category.name,
            "url_key": category.url_key,
            "seed_url": category.seed_url,
            "industry_ids": category.industry_ids,
            "site_total_count": category.total_count,
            "stored_listings": stored_listings,
            "last_scraped_at": _iso(category.last_scraped_at),
        }
        for category, stored_listings in rows
    ]


def list_scrape_runs(db: Session, limit: int = 20) -> list[dict[str, Any]]:
    runs = db.scalars(
        select(ScrapeRun).order_by(desc(ScrapeRun.started_at)).limit(limit)
    ).all()
    return [_run_to_dict(run) for run in runs]


def get_listing(db: Session, seek_id: int) -> dict[str, Any] | None:
    listing = db.get(BusinessListing, seek_id)
    if not listing:
        return None
    return listing_to_dict(listing, include_raw=True)


def list_listings(
    db: Session,
    category: str | None = None,
    state: str | None = None,
    opportunity_type: str | None = None,
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
    sort: str = "refresh_date",
    direction: str = "desc",
) -> dict[str, Any]:
    statement = select(BusinessListing)
    count_statement = select(func.count()).select_from(BusinessListing)

    filters = []
    if category:
        filters.append(BusinessListing.category_url_key == category)
    if state:
        filters.append(BusinessListing.state == state)
    if opportunity_type:
        filters.append(BusinessListing.opportunity_type == opportunity_type)
    if search:
        pattern = f"%{search}%"
        filters.append(
            or_(
                BusinessListing.title.ilike(pattern),
                BusinessListing.summary.ilike(pattern),
                BusinessListing.business_name.ilike(pattern),
                BusinessListing.location.ilike(pattern),
                BusinessListing.industry.ilike(pattern),
            )
        )

    for filter_clause in filters:
        statement = statement.where(filter_clause)
        count_statement = count_statement.where(filter_clause)

    sort_column = {
        "refresh_date": BusinessListing.refresh_date,
        "price_min": BusinessListing.price_min,
        "price_max": BusinessListing.price_max,
        "title": BusinessListing.title,
        "category": BusinessListing.category,
    }.get(sort, BusinessListing.refresh_date)
    statement = statement.order_by(_sort_direction(sort_column, direction))
    statement = statement.offset(offset).limit(limit)

    rows = db.scalars(statement).all()
    total = db.scalar(count_statement) or 0
    return {
        "count": len(rows),
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [listing_to_dict(row) for row in rows],
    }


def category_summary(db: Session) -> list[dict[str, Any]]:
    rows = db.execute(
        select(
            BusinessListing.category_url_key,
            BusinessListing.category,
            func.count(BusinessListing.seek_id),
            func.avg(BusinessListing.price_min),
            func.sum(case((BusinessListing.is_poa.is_(True), 1), else_=0)),
        )
        .group_by(BusinessListing.category_url_key, BusinessListing.category)
        .order_by(desc(func.count(BusinessListing.seek_id)))
    ).all()
    return [
        {
            "category_url_key": category_url_key,
            "category": category,
            "listings": listings,
            "average_price_min": round(average_price_min) if average_price_min else None,
            "poa_listings": poa_listings or 0,
        }
        for category_url_key, category, listings, average_price_min, poa_listings in rows
    ]


def _new_listing(
    scraped_listing: ScrapedListing,
    run_id: int | None,
    now: datetime,
) -> BusinessListing:
    return BusinessListing(
        **_listing_values(scraped_listing),
        first_seen_at=now,
        last_seen_at=now,
        last_seen_run_id=run_id,
    )


def _update_listing(
    listing: BusinessListing,
    scraped_listing: ScrapedListing,
    run_id: int | None,
    now: datetime,
) -> None:
    for key, value in _listing_values(scraped_listing).items():
        setattr(listing, key, value)
    listing.last_seen_at = now
    listing.last_seen_run_id = run_id


def _listing_values(scraped_listing: ScrapedListing) -> dict[str, Any]:
    return {
        "seek_id": scraped_listing.seek_id,
        "title": scraped_listing.title,
        "url_key": scraped_listing.url_key,
        "url": scraped_listing.url,
        "business_name": scraped_listing.business_name,
        "client_id": scraped_listing.client_id,
        "client_type": scraped_listing.client_type,
        "category": scraped_listing.category,
        "category_url_key": scraped_listing.category_url_key,
        "category_id": scraped_listing.category_id,
        "industry": scraped_listing.industry,
        "industry_url_key": scraped_listing.industry_url_key,
        "industry_id": scraped_listing.industry_id,
        "industry_tag": scraped_listing.industry_tag,
        "industry_tag_url_key": scraped_listing.industry_tag_url_key,
        "location": scraped_listing.location,
        "district_id": scraped_listing.district_id,
        "district_type": scraped_listing.district_type,
        "district_url_key": scraped_listing.district_url_key,
        "area": scraped_listing.area,
        "region": scraped_listing.region,
        "state": scraped_listing.state,
        "country": scraped_listing.country,
        "price_min": scraped_listing.price_min,
        "price_max": scraped_listing.price_max,
        "is_poa": scraped_listing.is_poa,
        "is_negotiable": scraped_listing.is_negotiable,
        "has_sav": scraped_listing.has_sav,
        "opportunity_type": scraped_listing.opportunity_type,
        "is_freemium": scraped_listing.is_freemium,
        "summary": scraped_listing.summary,
        "thumbnail_image_file_name": scraped_listing.thumbnail_image_file_name,
        "image_url": scraped_listing.image_url,
        "refresh_date": scraped_listing.refresh_date,
        "source_category_url_key": scraped_listing.source_category_url_key,
        "source_page": scraped_listing.source_page,
        "source_slot": scraped_listing.source_slot,
        "raw_json": scraped_listing.raw_json,
    }


def listing_to_dict(
    listing: BusinessListing,
    include_raw: bool = False,
) -> dict[str, Any]:
    data = {
        "seek_id": listing.seek_id,
        "title": listing.title,
        "url": listing.url,
        "business_name": listing.business_name,
        "client_id": listing.client_id,
        "client_type": listing.client_type,
        "category": listing.category,
        "category_url_key": listing.category_url_key,
        "industry": listing.industry,
        "industry_tag": listing.industry_tag,
        "location": listing.location,
        "area": listing.area,
        "region": listing.region,
        "state": listing.state,
        "country": listing.country,
        "price_min": listing.price_min,
        "price_max": listing.price_max,
        "is_poa": listing.is_poa,
        "is_negotiable": listing.is_negotiable,
        "has_sav": listing.has_sav,
        "opportunity_type": listing.opportunity_type,
        "summary": listing.summary,
        "image_url": listing.image_url,
        "refresh_date": _iso(listing.refresh_date),
        "first_seen_at": _iso(listing.first_seen_at),
        "last_seen_at": _iso(listing.last_seen_at),
        "source_page": listing.source_page,
        "source_slot": listing.source_slot,
    }
    if include_raw:
        data["raw_json"] = listing.raw_json
    return data


def _run_to_dict(run: ScrapeRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "started_at": _iso(run.started_at),
        "completed_at": _iso(run.completed_at),
        "status": run.status,
        "source": run.source,
        "days": run.days,
        "max_pages_per_category": run.max_pages_per_category,
        "categories_requested": run.categories_requested,
        "listings_scraped": run.listings_scraped,
        "listings_stored": run.listings_stored,
        "error": run.error,
    }


def _sort_direction(column: Any, direction: str) -> Any:
    if direction.lower() == "asc":
        return asc(column)
    return desc(column)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()
