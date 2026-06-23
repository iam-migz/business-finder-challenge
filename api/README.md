# API

Minimal FastAPI service for the GSPS challenge.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

## Run

```powershell
gsps-api
```

The hello world endpoint is available at:

```text
GET http://127.0.0.1:8000/
```

Run a category-organized scrape and store recent listings:

```text
POST http://127.0.0.1:8000/scrape?days=7&max_pages_per_category=20
```

The SQLite database file is created at `api/app.db` when the app starts.

Useful endpoints:

```text
GET /categories
GET /categories/summary
GET /listings
GET /listings?category=food-and-drink&limit=50
GET /listings/{seek_id}
GET /scrape/runs
POST /abs/scrape
GET /abs/releases
GET /abs/releases/{slug}
GET /ai/status
GET /ai/models
POST /ai/contact
POST /ai/complete
```

## AI configuration

The AI service uses an OpenAI-compatible endpoint. Configure it with:

```powershell
$env:OPENAI_API_KEY="provided-by-luke"
$env:OPENAI_BASE_URL="https://martial-miracle-critical-history.trycloudflare.com/v1"
$env:OPENAI_MODEL="smart"
```

`OPENAI_BASE_URL` defaults to the updated Cloudflare tunnel above, and `/v1` is appended automatically if omitted.
