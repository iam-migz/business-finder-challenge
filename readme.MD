# GSPS Challenge

Full-stack application for discovering and analyzing business-for-sale opportunities from Australia's **SEEK Business** marketplace, with AI-powered recommendation scoring.

## Tech Stack

### Backend (`api/`)

| Layer | Technology |
|---|---|
| Language | Python >= 3.11 |
| Framework | FastAPI + Uvicorn |
| ORM | SQLAlchemy |
| Database | SQLite (`api/app.db`) |
| Scraping | requests + BeautifulSoup4 |
| AI | OpenAI SDK (LiteLLM proxy, OpenAI-compatible) |

### Frontend (`client/`)

| Layer | Technology |
|---|---|
| Language | JavaScript (JSX) |
| Framework | React 19 + Vite 8 |
| Styling | Tailwind CSS 4 + shadcn/ui |
| State | TanStack React Query v5 |
| Tables | TanStack React Table v8 |

## Getting Started

### 1. Backend

```powershell
cd api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
gsps-api
```

The API starts on **http://127.0.0.1:8000**.

### 2. Frontend

```powershell
cd client
npm install
npm run dev
```

Vite proxies `/api/*` requests to the backend automatically.

### 3. AI Configuration

Set the following environment variables before starting the backend:

```powershell
$env:OPENAI_API_KEY="your-api-key"
$env:OPENAI_BASE_URL="https://martial-miracle-critical-history.trycloudflare.com/v1"
$env:OPENAI_MODEL="smart"
```

## Recommendation Strategy

We scrape **Australian Bureau of Statistics (ABS)** economic data and feed it to the AI as context, so it returns a grounded score and plain-English reason for each business listing or category.

### Data sources scraped

| ABS Release | Slug | What it provides |
|---|---|---|
| Business Indicators Australia | `business-indicators` | Quarterly estimates — company profits, sales growth, wages, inventories by industry. Includes HTML tables and XLSX/CSV downloads. |
| Australian Industry | `australian-industry` | Annual industry financials — operating profit before tax, EBITDA, sales income, wages, capital expenditure. |

The scraper (`api/app/services/abs_scraper.py`) extracts **key statistics**, **structured tables** (headers + rows), and **download links**. Data is persisted to SQLite via `api/app/services/abs_data.py` across `abs_releases`, `abs_tables`, `abs_table_rows`, and `abs_downloads` tables.

### How the AI scores listings

```
ABS website ──(scraper)──> SQLite (abs_releases / abs_tables / abs_table_rows)
                                      │
                              (context: key_statistics + table rows)
                                      │
SEEK listings ──(scraper)──> SQLite (business_listings)
                                      │
                              (listing: price, category, location, summary)
                                      │
                                      ▼
                              POST /ai/complete
                              { prompt, context }
                                      │
                                      ▼
                            AI Response
                            { score: 82, reason: "Stable B2B demand, lower capital...", risks: [...] }
```

1. **Scrape ABS** — `POST /abs/scrape` collects the latest releases and table data
2. **Retrieve data** — `GET /abs/releases/{slug}` returns structured economic data for the relevant industry
3. **Feed to AI** — Pass scraped key statistics and table rows as `context` to `POST /ai/complete` alongside a scoring prompt
4. **Score + Reason** — The AI returns a **0–100 score** and a **grounded explanation** based on real ABS data, not generic advice

The AI is guided by a 6-criteria scoring model (profitability 25%, demand 20%, risk 20%, competition 15%, capital fit 10%, listing quality 10%) — see [Recommendation Model](docs/recommendation.md) for the full framework.

## Key Endpoints

| Endpoint | Description |
|---|---|
| `GET /health` | Health check |
| `POST /scrape?days=7&max_pages_per_category=20` | Scrape SEEK Business listings |
| `GET /listings?category=food-and-drink&state=QLD` | Query listings |
| `GET /categories` | Category data |
| `POST /abs/scrape` | Scrape ABS releases |
| `GET /ai/status` | AI diagnostics |
| `POST /ai/complete` | AI completion |

## Documentation

- [Build Plan](docs/build_plan.md) — MVP feature plan
- [Recommendation Strategy](docs/recommendation.md) — AI-powered scoring using scraped ABS business indicators as context
- [SEEK Business Context](docs/seek_business_context.md) — Marketplace research
- [API README](api/README.md) — Backend setup and endpoints

## Next Steps / Improvements

While ABS data scraping is implemented, the following public Australian data sources are not yet integrated and would strengthen the recommendation engine:

| Data Source | Status | Value for scoring |
|---|---|---|
| **ABS Business Indicators** | Done | Quarterly profit, sales, wage, inventory trends by industry |
| **ABS Australian Industry** | Done | Annual industry financials — profit, EBITDA, sales income, capex |
| **ATO Small Business Benchmarks** | Not started | ~100 industry cost ratios (labour/turnover, rent/turnover) — detects abnormal listing financials |
| **ASIC Insolvency Statistics** | Not started | Insolvency rates by industry and state — risk scoring input |
| **ABS Counts of Australian Businesses** | Not started | Entry/exit rates, survival rates, business density — competition saturation |
| **ABS Household Spending** | Not started | Monthly spending by category — demand growth signal |
| **ABS Population / Regional Data** | Not started | Population growth, income levels by LGA — location attractiveness |

Integrating these would allow the AI to score all six criteria (profitability, demand, risk, competition, capital fit, listing quality) with real data rather than relying on the current two ABS releases + AI inference alone.
