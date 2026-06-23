from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag

ABS_BASE_URL = "https://www.abs.gov.au"
REQUEST_TIMEOUT_SECONDS = 25
USER_AGENT = "Mozilla/5.0 (compatible; GSPSChallengeBot/0.1)"

ABS_RELEASE_SOURCES = [
    {
        "slug": "business-indicators",
        "url": "https://www.abs.gov.au/statistics/economy/business-indicators/business-indicators-australia/latest-release",
    },
    {
        "slug": "australian-industry",
        "url": "https://www.abs.gov.au/statistics/industry/industry-overview/australian-industry/2024-25#data-downloads",
    },
]


@dataclass
class ScrapedABSRelease:
    slug: str
    title: str
    source_url: str
    description: str | None
    reference_period: str | None
    released: str | None
    release_date_time: str | None
    key_statistics: list[str]
    tables: list[dict[str, Any]]
    downloads: list[dict[str, Any]]


def scrape_abs_releases(slugs: list[str] | None = None) -> list[ScrapedABSRelease]:
    selected = {slug for slug in slugs or [] if slug}
    releases: list[ScrapedABSRelease] = []

    for source in ABS_RELEASE_SOURCES:
        if selected and source["slug"] not in selected:
            continue
        releases.append(scrape_abs_release(source["slug"], source["url"]))

    return releases


def scrape_abs_release(slug: str, url: str) -> ScrapedABSRelease:
    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    title = _clean_text(soup.find("h1")) or slug
    return ScrapedABSRelease(
        slug=slug,
        title=title,
        source_url=url.split("#", 1)[0],
        description=_page_description(soup),
        reference_period=_label_value(soup, "Reference period"),
        released=_label_value(soup, "Released"),
        release_date_time=_label_value(soup, "Release date and time"),
        key_statistics=_key_statistics(soup),
        tables=_tables(soup),
        downloads=_downloads(soup),
    )


def _page_description(soup: BeautifulSoup) -> str | None:
    h1 = soup.find("h1")
    if not h1:
        return None

    for sibling in h1.find_all_next(["p", "div"], limit=8):
        text = _clean_text(sibling)
        if text and text not in {"Latest release"}:
            return text
    return None


def _label_value(soup: BeautifulSoup, label: str) -> str | None:
    strings = [_normalize(value) for value in soup.stripped_strings]
    for index, value in enumerate(strings):
        if value == label and index + 1 < len(strings):
            return strings[index + 1]
    return None


def _key_statistics(soup: BeautifulSoup) -> list[str]:
    heading = _find_heading(soup, "Key statistics")
    if not heading:
        return []

    stats: list[str] = []
    for sibling in heading.find_all_next():
        if sibling is heading:
            continue
        if sibling.name in {"h2", "h3"}:
            break
        if sibling.name != "li":
            continue

        text = _clean_text(sibling)
        if not text or text.startswith("Download") or "Download table as" in text:
            continue
        stats.append(text)

    return stats


def _tables(soup: BeautifulSoup) -> list[dict[str, Any]]:
    parsed_tables: list[dict[str, Any]] = []
    for table_index, table in enumerate(soup.find_all("table")):
        title = _clean_text(table.find("caption")) or f"Table {table_index + 1}"
        headers = _headers(table)
        rows = _rows(table, headers)
        parsed_tables.append(
            {
                "table_index": table_index,
                "title": title,
                "headers": headers,
                "rows": rows,
            }
        )
    return parsed_tables


def _headers(table: Tag) -> list[str]:
    thead = table.find("thead")
    if not thead:
        first_row = table.find("tr")
        return [_clean_text(cell) or "" for cell in first_row.find_all(["th", "td"])] if first_row else []

    header_rows = thead.find_all("tr")
    grid: list[list[str]] = []
    occupied: dict[tuple[int, int], bool] = {}

    for row_index, row in enumerate(header_rows):
        grid.append([])
        column_index = 0
        for cell in row.find_all(["th", "td"]):
            while occupied.get((row_index, column_index)):
                column_index += 1

            text = _clean_text(cell) or ""
            colspan = int(cell.get("colspan", 1))
            rowspan = int(cell.get("rowspan", 1))

            for offset in range(colspan):
                while len(grid[row_index]) <= column_index + offset:
                    grid[row_index].append("")
                grid[row_index][column_index + offset] = text
                for row_offset in range(1, rowspan):
                    occupied[(row_index + row_offset, column_index + offset)] = True

            column_index += colspan

    width = max((len(row) for row in grid), default=0)
    headers: list[str] = []
    for column_index in range(width):
        parts = []
        for row in grid:
            value = row[column_index] if column_index < len(row) else ""
            if value and value not in parts:
                parts.append(value)
        headers.append(" - ".join(parts))

    return headers


def _rows(table: Tag, headers: list[str]) -> list[dict[str, Any]]:
    tbody = table.find("tbody") or table
    data_rows: list[dict[str, Any]] = []

    for row_index, row in enumerate(tbody.find_all("tr")):
        cells = row.find_all(["th", "td"])
        if not cells:
            continue

        label = _clean_text(cells[0])
        if not label:
            continue

        values: dict[str, str | float | None] = {}
        for column_index, cell in enumerate(cells[1:], start=1):
            header = headers[column_index] if column_index < len(headers) else f"Column {column_index}"
            values[header or f"Column {column_index}"] = _parse_number(_clean_text(cell))

        data_rows.append({"row_index": row_index, "label": label, "values": values})

    return data_rows


def _downloads(soup: BeautifulSoup) -> list[dict[str, Any]]:
    downloads: list[dict[str, Any]] = []

    for link in soup.find_all("a", href=True):
        href = link["href"]
        text = _clean_text(link) or ""
        href_lower = href.lower()
        if not any(extension in href_lower for extension in (".xlsx", ".zip", ".csv")):
            continue

        title = _download_title(link, fallback=text)
        file_type = href_lower.rsplit(".", 1)[-1].split("?", 1)[0]
        downloads.append(
            {
                "title": title,
                "href": urljoin(ABS_BASE_URL, href),
                "file_type": file_type,
                "size_label": _size_label(text),
            }
        )

    return downloads


def _download_title(link: Tag, fallback: str) -> str:
    heading = link.find_previous(["h3", "h4", "caption"])
    title = _clean_text(heading)
    return title or fallback or "Download"


def _size_label(text: str) -> str | None:
    if "[" not in text or "]" not in text:
        return None
    return text.split("[", 1)[1].split("]", 1)[0]


def _find_heading(soup: BeautifulSoup, text: str) -> Tag | None:
    for heading in soup.find_all(["h2", "h3"]):
        if _clean_text(heading) == text:
            return heading
    return None


def _parse_number(value: str | None) -> str | float | None:
    if value is None:
        return None
    candidate = value.replace(",", "").replace("$", "").strip()
    if candidate in {"", "na", "n/a", "-"}:
        return value
    try:
        return float(candidate)
    except ValueError:
        return value


def _clean_text(element: Tag | str | None) -> str | None:
    if element is None:
        return None
    if isinstance(element, str):
        return _normalize(element)
    return _normalize(element.get_text(" ", strip=True))


def _normalize(value: str) -> str:
    return " ".join(value.split())
