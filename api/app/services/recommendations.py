from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ABSTable, ABSTableRow, BusinessListing


@dataclass(frozen=True)
class BusinessIndicatorContext:
    profit_by_industry: dict[str, float]
    wages_by_industry: dict[str, float]
    inventory_by_industry: dict[str, float]
    sales_by_industry: dict[str, float]


@dataclass(frozen=True)
class ListingRecommendation:
    score: int
    reason: str
    abs_industry: str | None


def load_business_indicator_context(db: Session) -> BusinessIndicatorContext:
    return BusinessIndicatorContext(
        profit_by_industry=_load_indicator_table(db, "CGOP by industry"),
        wages_by_industry=_load_indicator_table(db, "Wages by industry"),
        inventory_by_industry=_load_indicator_table(db, "Inventories by industry"),
        sales_by_industry=_load_indicator_table(db, "Sales by industry"),
    )


def recommend_listing(
    listing: BusinessListing,
    context: BusinessIndicatorContext,
) -> ListingRecommendation:
    abs_industry = _map_listing_to_abs_industry(listing)
    if not abs_industry:
        return ListingRecommendation(
            score=50,
            reason="No close ABS industry match; score is neutral until richer matching is added.",
            abs_industry=None,
        )

    sales = context.sales_by_industry.get(abs_industry)
    profit = context.profit_by_industry.get(abs_industry)
    wages = context.wages_by_industry.get(abs_industry)
    inventory = context.inventory_by_industry.get(abs_industry)

    score = 55
    reasons: list[str] = [f"Mapped to ABS {abs_industry}."]

    if sales is not None:
        score += sales * 8
        reasons.append(f"Sales changed {sales:+.1f}% q/q.")
    if profit is not None:
        score += profit * 3
        reasons.append(f"Operating profit changed {profit:+.1f}% q/q.")
    if wages is not None:
        wage_penalty = max(wages - 1.0, 0) * 2
        score -= wage_penalty
        reasons.append(f"Wages changed {wages:+.1f}% q/q.")
    if inventory is not None:
        score += inventory * 1
        reasons.append(f"Inventories changed {inventory:+.1f}% q/q.")

    if listing.price_min is not None and listing.price_min <= 150_000:
        score += 4
        reasons.append("Lower entry price improves screenability.")
    elif listing.is_poa:
        score -= 3
        reasons.append("P.O.A reduces price transparency.")

    return ListingRecommendation(
        score=max(0, min(100, round(score))),
        reason=" ".join(reasons),
        abs_industry=abs_industry,
    )


def _load_indicator_table(db: Session, title_prefix: str) -> dict[str, float]:
    table = db.scalars(
        select(ABSTable)
        .where(
            ABSTable.release_slug == "business-indicators",
            ABSTable.title.ilike(f"{title_prefix}%"),
        )
        .order_by(ABSTable.table_index)
        .limit(1)
    ).first()
    if not table:
        return {}

    rows = db.scalars(
        select(ABSTableRow)
        .where(ABSTableRow.table_id == table.id)
        .order_by(ABSTableRow.row_index)
    ).all()

    values: dict[str, float] = {}
    for row in rows:
        value = row.values.get("Quarterly change (%)")
        if isinstance(value, int | float):
            values[row.label] = float(value)
    return values


def _map_listing_to_abs_industry(listing: BusinessListing) -> str | None:
    text = " ".join(
        value or ""
        for value in (
            listing.category,
            listing.industry,
            listing.industry_tag,
            listing.title,
            listing.summary,
        )
    ).lower()

    if any(term in text for term in ("cafe", "restaurant", "takeaway", "food", "drink", "bar", "bakery")):
        return "Accommodation and Food Services"
    if any(term in text for term in ("motel", "hotel", "tourism", "travel", "accommodation")):
        return "Accommodation and Food Services"
    if any(term in text for term in ("retail", "store", "shop", "fashion", "grocery", "liquor")):
        return "Retail Trade"
    if any(term in text for term in ("cleaning", "maintenance", "admin", "support")):
        return "Administrative and Support Services"
    if any(term in text for term in ("health", "medical", "aged care", "fitness", "beauty")):
        return "Health Care and Social Assistance"
    if any(term in text for term in ("education", "training", "childcare", "learning")):
        return "Education and Training"
    if any(term in text for term in ("transport", "logistics", "warehouse", "distribution")):
        return "Transport, Postal and Warehousing"
    if any(term in text for term in ("property", "real estate", "rental", "hire")):
        return "Rental, Hiring and Real Estate Services"
    if any(term in text for term in ("professional", "consult", "account", "broker", "business service")):
        return "Professional, Scientific and Technical Services"
    if any(term in text for term in ("entertainment", "amusement", "recreation", "leisure", "sport")):
        return "Arts and Recreation Services"
    if any(term in text for term in ("construction", "building", "trade")):
        return "Construction"
    if any(term in text for term in ("manufacturing", "wholesale")):
        return "Manufacturing"
    if "commercial services" in text:
        return "Professional, Scientific and Technical Services"
    if "personal services" in text or "miscellaneous" in text:
        return "Other Services"
    return None
