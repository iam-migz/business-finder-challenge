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
    signals: list[str] = []

    if sales is not None:
        score += sales * 8
        signals.append(_sales_signal(sales))
    if profit is not None:
        score += profit * 3
        signals.append(_profit_signal(profit))
    if wages is not None:
        wage_penalty = max(wages - 1.0, 0) * 2
        score -= wage_penalty
        signals.append(_wage_signal(wages))
    if inventory is not None:
        score += inventory * 1
        signals.append(_inventory_signal(inventory))

    if listing.price_min is not None and listing.price_min <= 150_000:
        score += 4
        signals.append("The lower advertised entry price makes this easier to screen quickly.")
    elif listing.is_poa:
        score -= 3
        signals.append("The P.O.A. price means extra diligence is needed before comparing value.")

    return ListingRecommendation(
        score=max(0, min(100, round(score))),
        reason=_recommendation_reason(abs_industry, signals),
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


def _recommendation_reason(abs_industry: str, signals: list[str]) -> str:
    if not signals:
        return (
            f"This opportunity sits in {abs_industry}. ABS data has limited fresh movement "
            "signals for this industry, so treat the score as a neutral starting point."
        )

    summary = " ".join(signals[:3])
    if len(signals) > 3:
        summary = f"{summary} {signals[3]}"
    return f"This opportunity appears closest to {abs_industry}. {summary}"


def _sales_signal(value: float) -> str:
    if value >= 1.0:
        return "Recent sales growth suggests demand is improving in this market."
    if value > 0:
        return "Sales are slightly positive, which points to steady but modest demand."
    if value <= -1.0:
        return "Sales have softened, so revenue resilience should be checked carefully."
    return "Sales are broadly flat, so the individual business performance matters more."


def _profit_signal(value: float) -> str:
    if value >= 5.0:
        return "Profit momentum is strong, which is a positive sector signal."
    if value > 0:
        return "Profit is moving in the right direction, adding some confidence."
    if value <= -5.0:
        return "Sector profit is under pressure, so margins deserve close review."
    return "Profit has weakened slightly, making margin quality important."


def _wage_signal(value: float) -> str:
    if value >= 2.0:
        return "Wage costs are rising, which may pressure margins for labour-heavy operators."
    if value > 0:
        return "Wage growth looks manageable, but staffing costs still need checking."
    return "Wage pressure is low in the latest ABS data, which may help operating margins."


def _inventory_signal(value: float) -> str:
    if value >= 2.0:
        return "Inventory is building, which can support sales but may tie up cash."
    if value > 0:
        return "Inventory is growing modestly, suggesting operators are preparing for demand."
    if value <= -2.0:
        return "Inventory has fallen, which may indicate cautious demand or tighter stock control."
    return "Inventory is slightly lower, so stock-dependent businesses need closer review."


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
