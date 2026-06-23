from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from requests import RequestException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db, initialize_database
from app.models import ScrapeRun
from app.services.abs_data import abs_release_detail, abs_release_summary, persist_abs_releases
from app.services.abs_scraper import scrape_abs_releases
from app.services.ai import ai_error_response, ai_status, create_ai_service
from app.services.listings import (
    category_summary,
    get_listing,
    list_categories,
    list_listings,
    list_scrape_runs,
    persist_scrape_result,
)
from app.services.scraper import SEEK_BUSINESS_URL, scrape_seek_business


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    initialize_database()
    yield


app = FastAPI(title="GSPS Challenge API", lifespan=lifespan)


class AICompletionRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4000)
    context: dict[str, object] | list[object] | str | None = None
    temperature: float = Field(0.2, ge=0, le=2)
    max_tokens: int = Field(500, ge=1, le=2000)


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "Hello World"}


@app.get("/health")
def health_check(db: Session = Depends(get_db)) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}


@app.get("/ai/status")
def get_ai_status() -> dict[str, object]:
    return ai_status()


@app.post("/ai/contact")
def ai_contact() -> dict[str, object]:
    try:
        response = create_ai_service().contact()
    except Exception as exc:
        return ai_error_response(exc)

    return {
        "ok": True,
        "message": response.content,
        "model": response.model,
        "usage": response.usage,
    }


@app.get("/ai/models")
def ai_models() -> dict[str, object]:
    try:
        models = create_ai_service().list_models()
    except Exception as exc:
        return ai_error_response(exc)

    return {"ok": True, "data": models}


@app.post("/ai/complete")
def ai_complete(request: AICompletionRequest) -> dict[str, object]:
    try:
        response = create_ai_service().complete(
            prompt=request.prompt,
            context=request.context,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
    except Exception as exc:
        return ai_error_response(exc)

    return {
        "ok": True,
        "message": response.content,
        "model": response.model,
        "usage": response.usage,
    }


@app.get("/scrape")
def scrape_legacy(
    db: Session = Depends(get_db),
    days: int = Query(7, ge=1, le=30),
    max_pages_per_category: int = Query(20, ge=1, le=100),
    category: list[str] | None = Query(default=None),
) -> dict[str, object]:
    return run_scrape(
        db=db,
        days=days,
        max_pages_per_category=max_pages_per_category,
        category=category,
    )


@app.post("/scrape")
def run_scrape(
    db: Session = Depends(get_db),
    days: int = Query(7, ge=1, le=30),
    max_pages_per_category: int = Query(20, ge=1, le=100),
    category: list[str] | None = Query(default=None),
) -> dict[str, object]:
    run = ScrapeRun(
        source=SEEK_BUSINESS_URL,
        days=days,
        max_pages_per_category=max_pages_per_category,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        result = scrape_seek_business(
            days=days,
            max_pages_per_category=max_pages_per_category,
            category_keys=category,
        )
        stored = persist_scrape_result(db, result, run)
        run.status = "completed_with_errors" if result.errors else "completed"
        run.completed_at = datetime.now(UTC)
        run.categories_requested = len(result.categories)
        run.listings_scraped = len(result.listings)
        run.listings_stored = stored
        run.error = "\n".join(result.errors) or None
        db.commit()
    except RequestException as exc:
        run.status = "failed"
        run.completed_at = datetime.now(UTC)
        run.error = str(exc)
        db.commit()
        return {
            "source": SEEK_BUSINESS_URL,
            "count": 0,
            "stored": 0,
            "run_id": run.id,
            "error": str(exc),
            "data": [],
        }

    return {
        "source": SEEK_BUSINESS_URL,
        "run_id": run.id,
        "days": result.days,
        "cutoff": result.cutoff.isoformat(),
        "categories": [category.name for category in result.categories],
        "count": len(result.listings),
        "stored": stored,
        "errors": result.errors,
        "data": [listing.to_dict() for listing in result.listings],
    }


@app.get("/scrape/runs")
def scrape_runs(
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
) -> dict[str, object]:
    return {"data": list_scrape_runs(db, limit=limit)}


@app.get("/categories")
def categories(db: Session = Depends(get_db)) -> dict[str, object]:
    return {"data": list_categories(db)}


@app.get("/categories/summary")
def categories_summary(db: Session = Depends(get_db)) -> dict[str, object]:
    return {"data": category_summary(db)}


@app.get("/listings")
def listings(
    db: Session = Depends(get_db),
    category: str | None = None,
    state: str | None = None,
    opportunity_type: str | None = None,
    search: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    sort: str = Query("refresh_date"),
    direction: str = Query("desc"),
) -> dict[str, object]:
    return list_listings(
        db,
        category=category,
        state=state,
        opportunity_type=opportunity_type,
        search=search,
        limit=limit,
        offset=offset,
        sort=sort,
        direction=direction,
    )


@app.get("/listings/{seek_id}")
def listing(seek_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    listing_data = get_listing(db, seek_id)
    if not listing_data:
        raise HTTPException(status_code=404, detail="Listing not found")
    return listing_data


@app.post("/abs/scrape")
def scrape_abs(
    db: Session = Depends(get_db),
    slug: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        releases = scrape_abs_releases(slugs=slug)
        stored = persist_abs_releases(db, releases)
        db.commit()
    except RequestException as exc:
        db.rollback()
        return {"count": 0, "stored": 0, "error": str(exc), "data": []}

    return {
        "count": len(releases),
        "stored": stored,
        "data": [
            {
                "slug": release.slug,
                "title": release.title,
                "reference_period": release.reference_period,
                "tables": len(release.tables),
                "downloads": len(release.downloads),
                "key_statistics": release.key_statistics,
            }
            for release in releases
        ],
    }


@app.get("/abs/releases")
def abs_releases(db: Session = Depends(get_db)) -> dict[str, object]:
    return abs_release_summary(db)


@app.get("/abs/releases/{slug}")
def abs_release(slug: str, db: Session = Depends(get_db)) -> dict[str, object]:
    release = abs_release_detail(db, slug)
    if not release:
        raise HTTPException(status_code=404, detail="ABS release not found")
    return release


def start() -> None:
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
