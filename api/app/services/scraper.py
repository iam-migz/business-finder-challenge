from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import requests
from bs4 import BeautifulSoup

SEEK_BUSINESS_URL = "https://www.seekbusiness.com.au"
GRAPHQL_URL = f"{SEEK_BUSINESS_URL}/graphql"
REQUEST_TIMEOUT_SECONDS = 25
USER_AGENT = "Mozilla/5.0 (compatible; GSPSChallengeBot/0.1)"
PAGE_SIZE = 18

CATEGORY_SEEDS = [
    ("Food & Drink", "food-and-drink"),
    ("Health, Beauty & Fitness", "health-beauty-fitness"),
    ("Retail", "retail"),
    ("Commercial Services", "commercial-services"),
    ("Personal Services", "personal-services"),
    ("Cleaning & Maintenance", "cleaning-and-maintenance"),
    ("Accommodation, Tourism & Leisure", "accommodation-tourism-leisure"),
    ("Miscellaneous", "miscellaneous-industries"),
]

SEARCH_LISTINGS_QUERY = """
query GetMorePageSearchResultsSearchCriteria($queryInput: PublicListingSearchInput!) {
  searchListings(queryInput: $queryInput) {
    page
    pageSize
    totalCount
    organicListings {
      ...SearchListingFields
    }
    premiumListings {
      ...SearchListingFields
    }
    expandedListings {
      ...SearchListingFields
    }
    industries {
      industryId
      industryGroupId
      title
      urlKey
      count
    }
  }
}

fragment SearchListingFields on SearchListing {
  id
  businessName
  client {
    id
    type
    profileLogoImageFileName
  }
  district {
    id
    displayTitle
    type
    urlKey
    area {
      id
      title
      urlKey
    }
    region {
      id
      title
      urlKey
    }
    state {
      id
      title
      urlKey
    }
    country {
      id
      title
      urlKey
    }
  }
  gccFreeText
  industry {
    id
    title
    urlKey
  }
  industryGroup {
    title
    urlKey
    industryGroupId
  }
  industryTag {
    id
    title
    urlKey
    associatedIndustryIds
  }
  investment {
    range {
      min
      max
    }
    isPoa
    isNegotiable
    hasInventorySav
  }
  isFreemium
  showThumbnailImageOnSerp
  opportunityType
  refreshDate
  summary
  thumbnailImageFileName
  title
  urlKey
}
"""


@dataclass(frozen=True)
class ScrapeCategory:
    name: str
    url_key: str
    seed_url: str
    industry_ids: list[str]
    total_count: int | None = None


@dataclass
class ScrapedListing:
    seek_id: int
    title: str
    url_key: str
    url: str
    business_name: str | None
    client_id: int | None
    client_type: str | None
    category: str | None
    category_url_key: str | None
    category_id: int | None
    industry: str | None
    industry_url_key: str | None
    industry_id: int | None
    industry_tag: str | None
    industry_tag_url_key: str | None
    location: str | None
    district_id: str | None
    district_type: str | None
    district_url_key: str | None
    area: str | None
    region: str | None
    state: str | None
    country: str | None
    price_min: int | None
    price_max: int | None
    is_poa: bool
    is_negotiable: bool
    has_sav: bool
    opportunity_type: str | None
    is_freemium: bool
    summary: str | None
    thumbnail_image_file_name: str | None
    image_url: str | None
    refresh_date: datetime | None
    source_category_url_key: str
    source_page: int
    source_slot: str
    raw_json: dict[str, Any] = field(repr=False)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.refresh_date:
            data["refresh_date"] = self.refresh_date.isoformat()
        return data


@dataclass
class ScrapeResult:
    source: str
    days: int
    cutoff: datetime
    categories: list[ScrapeCategory]
    listings: list[ScrapedListing]
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "days": self.days,
            "cutoff": self.cutoff.isoformat(),
            "categories": [asdict(category) for category in self.categories],
            "count": len(self.listings),
            "errors": self.errors,
            "data": [listing.to_dict() for listing in self.listings],
        }


def scrape_seek_business(
    days: int = 7,
    max_pages_per_category: int = 20,
    category_keys: list[str] | None = None,
) -> ScrapeResult:
    cutoff = datetime.now(UTC) - timedelta(days=days)
    categories = _load_categories(category_keys)
    listings_by_id: dict[int, ScrapedListing] = {}
    errors: list[str] = []

    for category in categories:
        try:
            _scrape_category(
                category=category,
                cutoff=cutoff,
                max_pages=max_pages_per_category,
                listings_by_id=listings_by_id,
            )
        except requests.RequestException as exc:
            errors.append(f"{category.name}: {exc}")

    return ScrapeResult(
        source=SEEK_BUSINESS_URL,
        days=days,
        cutoff=cutoff,
        categories=categories,
        listings=list(listings_by_id.values()),
        errors=errors,
    )


def _load_categories(category_keys: list[str] | None) -> list[ScrapeCategory]:
    selected = {
        category_key.strip()
        for category_key in category_keys or []
        if category_key.strip()
    }
    categories: list[ScrapeCategory] = []

    for name, url_key in CATEGORY_SEEDS:
        if selected and url_key not in selected:
            continue

        seed_url = f"{SEEK_BUSINESS_URL}/businesses-for-sale/within-{url_key}"
        category = _category_from_seed_page(name=name, url_key=url_key, seed_url=seed_url)
        categories.append(category)

    return categories


def _category_from_seed_page(name: str, url_key: str, seed_url: str) -> ScrapeCategory:
    response = requests.get(
        seed_url,
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    next_data_script = soup.find("script", id="__NEXT_DATA__")
    if next_data_script is None or not next_data_script.string:
        return ScrapeCategory(name=name, url_key=url_key, seed_url=seed_url, industry_ids=[])

    import json

    data = json.loads(next_data_script.string)
    page_props = data.get("props", {}).get("pageProps", {})
    search_criteria = page_props.get("searchCriteria", {})
    apollo_state = page_props.get("__APOLLO_STATE__", {})
    search_listings = apollo_state.get("ROOT_QUERY", {}).get("searchListings", {})

    industry_ids = [
        str(industry.get("id"))
        for industry in search_criteria.get("industries") or []
        if industry.get("id") is not None
    ]
    total_count = search_listings.get("totalCount")

    return ScrapeCategory(
        name=name,
        url_key=url_key,
        seed_url=seed_url,
        industry_ids=industry_ids,
        total_count=total_count,
    )


def _scrape_category(
    category: ScrapeCategory,
    cutoff: datetime,
    max_pages: int,
    listings_by_id: dict[int, ScrapedListing],
) -> None:
    if not category.industry_ids:
        return

    for page in range(max_pages):
        payload = {
            "operationName": "GetMorePageSearchResultsSearchCriteria",
            "query": SEARCH_LISTINGS_QUERY,
            "variables": {
                "queryInput": {
                    "criteria": {"industryIds": category.industry_ids},
                    "includePremium": True,
                    "page": page,
                    "pageSize": PAGE_SIZE,
                }
            },
        }
        response = requests.post(
            GRAPHQL_URL,
            json=payload,
            headers={"User-Agent": USER_AGENT, "Content-Type": "application/json"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("errors"):
            raise requests.RequestException(str(data["errors"]))

        search_listings = data.get("data", {}).get("searchListings") or {}
        page_listings = _extract_page_listings(search_listings, category, page)
        if not page_listings:
            break

        recent_listings = [
            listing
            for listing in page_listings
            if listing.refresh_date is None or listing.refresh_date >= cutoff
        ]
        for listing in recent_listings:
            listings_by_id[listing.seek_id] = listing

        organic_listings = [
            listing for listing in page_listings if listing.source_slot == "organic"
        ]
        if organic_listings and all(
            listing.refresh_date and listing.refresh_date < cutoff
            for listing in organic_listings
        ):
            break


def _extract_page_listings(
    search_listings: dict[str, Any],
    category: ScrapeCategory,
    page: int,
) -> list[ScrapedListing]:
    listings: list[ScrapedListing] = []

    for slot_name in ("premium", "organic", "expanded"):
        source_key = f"{slot_name}Listings"
        for raw_listing in search_listings.get(source_key) or []:
            listing = _parse_listing(raw_listing, category, page, slot_name)
            if listing:
                listings.append(listing)

    return listings


def _parse_listing(
    raw_listing: dict[str, Any],
    category: ScrapeCategory,
    page: int,
    source_slot: str,
) -> ScrapedListing | None:
    seek_id = raw_listing.get("id")
    title = _clean_text(raw_listing.get("title"))
    url_key = raw_listing.get("urlKey")
    if not seek_id or not title or not url_key:
        return None

    client = raw_listing.get("client") or {}
    district = raw_listing.get("district") or {}
    industry = raw_listing.get("industry") or {}
    industry_group = raw_listing.get("industryGroup") or {}
    industry_tag = raw_listing.get("industryTag") or {}
    investment = raw_listing.get("investment") or {}
    investment_range = investment.get("range") or {}

    refresh_date = _parse_datetime(raw_listing.get("refreshDate"))
    client_id = _to_int(client.get("id"))

    return ScrapedListing(
        seek_id=int(seek_id),
        title=title,
        url_key=url_key,
        url=f"{SEEK_BUSINESS_URL}/business-listing/{url_key}/{seek_id}",
        business_name=_clean_text(raw_listing.get("businessName")),
        client_id=client_id,
        client_type=_clean_text(client.get("type")),
        category=_clean_text(industry_group.get("title")) or category.name,
        category_url_key=industry_group.get("urlKey") or category.url_key,
        category_id=_to_int(industry_group.get("industryGroupId")),
        industry=_clean_text(industry.get("title")),
        industry_url_key=industry.get("urlKey"),
        industry_id=_to_int(industry.get("id")),
        industry_tag=_clean_text(industry_tag.get("title")),
        industry_tag_url_key=industry_tag.get("urlKey"),
        location=_clean_text(district.get("displayTitle")),
        district_id=str(district.get("id")) if district.get("id") is not None else None,
        district_type=district.get("type"),
        district_url_key=district.get("urlKey"),
        area=_location_title(district.get("area")),
        region=_location_title(district.get("region")),
        state=_location_title(district.get("state")),
        country=_location_title(district.get("country")),
        price_min=_to_int(investment_range.get("min")),
        price_max=_to_int(investment_range.get("max")),
        is_poa=bool(investment.get("isPoa")),
        is_negotiable=bool(investment.get("isNegotiable")),
        has_sav=bool(investment.get("hasInventorySav")),
        opportunity_type=raw_listing.get("opportunityType"),
        is_freemium=bool(raw_listing.get("isFreemium")),
        summary=_clean_text(raw_listing.get("summary")),
        thumbnail_image_file_name=raw_listing.get("thumbnailImageFileName"),
        image_url=_image_url(client_id, raw_listing.get("thumbnailImageFileName")),
        refresh_date=refresh_date,
        source_category_url_key=category.url_key,
        source_page=page,
        source_slot=source_slot,
        raw_json=raw_listing,
    )


def _image_url(client_id: int | None, file_name: str | None) -> str | None:
    if not client_id or not file_name:
        return None
    return f"https://images.seekbusiness.com.au/client/original/{client_id}/260x195/{file_name}"


def _location_title(value: dict[str, Any] | None) -> str | None:
    if not value:
        return None
    return _clean_text(value.get("title"))


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    return parsed.astimezone(UTC)


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text or None


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
