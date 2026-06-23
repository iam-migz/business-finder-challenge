# Recommendation Strategy

## How it works (implemented)

We scrape **Australian Bureau of Statistics (ABS)** publicly available economic data and feed it to the AI as additional context to generate a recommendation score and a human-readable reason for each business listing or category.

### Data sources we scrape

| ABS Release | Slug | What it provides |
|---|---|---|
| Business Indicators Australia | `business-indicators` | Quarterly estimates for company gross operating profits, sales growth, wages, and inventories by industry — available as HTML tables with key statistics and downloadable XLSX/CSV files |
| Australian Industry | `australian-industry` | Annual industry-level financial performance data including operating profit before tax, EBITDA, sales and service income, wages, and capital expenditure |

The scraper (`api/app/services/abs_scraper.py`) fetches each release page, extracts:

- **Key statistics** — headline figures like profit growth, sales growth, wage pressure, and inventory movement
- **Tables** — structured data with headers and rows (e.g. industry name → profit, sales, wages values)
- **Downloads** — links to full XLSX/CSV datasets for deeper analysis

All scraped data is persisted to SQLite via `api/app/services/abs_data.py` in four tables: `abs_releases`, `abs_tables`, `abs_table_rows`, and `abs_downloads`.

### How the AI uses this data

The recommendation pipeline:

1. **Scrape** — Run `POST /abs/scrape` to collect the latest ABS releases and their table data
2. **Retrieve** — Query `GET /abs/releases/{slug}` to get structured economic data for the relevant industry
3. **Feed to AI** — Pass the scraped key statistics and table row data as `context` to `POST /ai/complete` alongside a prompt like _"Score this business category based on profitability, demand, and risk"_
4. **Score + Reason** — The AI (LiteLLM proxy, OpenAI-compatible) returns a numeric score (0–100) and a plain-English explanation grounded in the ABS data

The AI service (`api/app/services/ai.py`) uses the OpenAI SDK configured via environment variables:

```powershell
$env:OPENAI_API_KEY="your-api-key"
$env:OPENAI_BASE_URL="https://martial-miracle-critical-history.trycloudflare.com/v1"
$env:OPENAI_MODEL="smart"
```

### Architecture

```
ABS website ──(scraper)──> SQLite (abs_releases / abs_tables / abs_table_rows)
                                      │
                              (context: key_statistics + table rows)
                                      │
SEEK listings ──(scraper)──> SQLite (business_listings)
                                      │
                              (listing data: price, category, location, summary)
                                      │
                                      ▼
                              POST /ai/complete
                              { prompt, context }
                                      │
                                      ▼
                            AI Response
                            { score: 82, reason: "Stable B2B demand, lower capital...", risks: [...] }
```

The AI returns both a **score** and a **reason** grounded in the real ABS data, not just generic advice.

---

## Theoretical scoring model

Below is the detailed scoring framework the AI uses as guidance.

1. First, define what we are recommending

We are not recommending one exact listing yet. We are recommending a business category or opportunity type, for example:

Cafe
Cleaning business
Laundromat
Gym / Pilates studio
NDIS service provider
Online retail
Franchise bakery
Commercial cleaning
Mobile car detailing
Accounting/bookkeeping service
Childcare
Convenience store
Courier / logistics business

Then later, we can score actual listings from SEEK Business using the same framework.

So the system has two levels:

Level	Example	Purpose
Industry/category recommendation	“Commercial cleaning in Brisbane looks attractive”	Helps user know what kind of business to search for
Listing recommendation	“This cleaning business listing looks better than this cafe listing”	Helps user compare actual opportunities
2. Use public Australian data sources

For Australia, we can build a useful model using public or semi-public data.

A. ABS industry profitability data

The Australian Bureau of Statistics publishes industry financial performance data, including income, expenses, profit, and capital expenditure. Its Australian Industry release is one of the best baseline sources for industry-level profitability. The latest page shows the 2024–25 financial year release as the latest release.

Useful fields from ABS:

Operating profit before tax
EBITDA
Sales and service income
Wages and salaries
Industry value added
Capital expenditure
Industry growth/decline

This gives us a macro view of which sectors are actually making money.

B. ABS Business Indicators

ABS Business Indicators gives quarterly estimates for private-sector sales, wages, profits, and inventories. The March 2026 release says company gross operating profits fell 1.3% in the quarter, wages rose 1.2%, and sales rose in 10 industries while falling in 5. It also shows industry-level movements such as mining profit decline and construction profit growth.

This is useful because it is more recent than annual data.

Useful fields:

Quarterly profit growth
Sales growth
Wage pressure
Inventory movement
Industry momentum
C. ABS business counts, entries, and exits

ABS Counts of Australian Businesses is very important for understanding market saturation and failure risk. At 30 June 2025, Australia had 2,729,648 actively trading businesses, with a 16.4% entry rate and 13.9% exit rate in 2024–25.

Useful fields:

Number of businesses by industry
Entry rate
Exit rate
Net business growth
Survival rates
Employing vs non-employing businesses

This helps answer: “Are businesses in this category growing or dying?”

D. ATO small business benchmarks

The Australian Taxation Office publishes small business benchmarks for around 100 industries. The ATO says the 2023–24 benchmarks help compare business performance against similar businesses in the same industry.

This is especially useful because ABS data is broad, while ATO benchmarks are closer to small-business reality.

Useful fields:

Cost of sales to turnover
Rent to turnover
Labour to turnover
Motor vehicle expenses
Benchmark operating ranges by industry

This helps detect if a listing’s numbers look abnormal.

E. ASIC insolvency statistics

ASIC publishes insolvency statistics based on forms and reports lodged against corporate registers.

This is important for risk scoring. A business category might have good revenue but high insolvency risk. For example, construction and hospitality have been under pressure in Australia in recent years.

Useful fields:

Insolvencies by industry
Insolvencies by state
External administration trends
Industry stress levels
F. ABS population and regional data

For local recommendations, we need location data. ABS Data by Region provides data by Local Government Areas and other geographies, including population, economy, industry, income, employment, education, and health.

ABS also publishes regional population data showing population change by Local Government Area.

Useful fields:

Population growth
Income levels
Age distribution
Employment
Local business counts
Regional economic indicators

This helps answer: “Is this business category good in this location?”

G. Household spending data

ABS Monthly Household Spending Indicator tracks spending by category. The April 2026 release said spending decreased in six of nine categories, with the largest decreases in transport, clothing and footwear, and food.

Useful fields:

Spending by category
Spending growth/decline
State-level spending trends
Discretionary vs non-discretionary demand

This helps determine whether consumer demand is rising or falling.

H. SEEK Business marketplace data

From SEEK Business itself, we can collect:

Asking price
Industry/category
Location
Listing type
Franchise vs independent
Business description
Broker/seller
Date listed
Revenue/profit claims, if shown
Price changes over time
Listing age
Removed listings

This gives us supply-side marketplace signals.

3. Define the recommendation criteria

I would define the score using six major criteria.

Criteria 1: Profitability

This answers:

Does this type of business usually make money?

Possible metrics:

Metric	Meaning
Profit margin	How much profit remains after costs
EBITDA margin	Operating profitability before financing/tax/depreciation
Profit growth	Is profitability improving or worsening?
Revenue-to-cost ratio	How efficient the business model is
Wage-to-sales ratio	How labour-heavy the business is
Rent-to-sales ratio	How location-cost-sensitive it is

Example: a Pilates studio might have attractive margins, but a restaurant might have thin margins due to food, rent, and labour.

IBISWorld’s public ranking lists high-margin industries in Australia, including superannuation funds, commercial real estate agents, NDIS providers, electricity distribution, online car classifieds, outplacement services, stevedoring services, and Pilates/yoga studios.

But we should not blindly recommend all of these. Some are not realistic small-business opportunities.

For example:

Superannuation funds = profitable, but not realistic for a small buyer.
Electricity distribution = profitable, but regulated and capital-heavy.
Pilates/yoga studios = more realistic as a small business.
Commercial real estate agency = realistic if buyer has skills/licensing.

So profitability must be filtered by feasibility.

Criteria 2: Demand

This answers:

Is there enough customer demand?

Possible metrics:

Metric	Source
Household spending growth	ABS Monthly Household Spending
Search demand	Google Trends
Population growth	ABS Regional Population
Local income	ABS Data by Region
Category growth	ABS/IBISWorld
Franchise expansion	SEEK Business listings
Number of new businesses entering category	ABS business entries

Demand should be measured both nationally and locally.

Example:

A cafe might have strong demand in a growing suburb, but weak demand in a CBD area with declining foot traffic.

A cleaning business may have stable demand because both households and businesses need it regardless of economic cycles.

Criteria 3: Risk / failure rate

This answers:

How likely is this business type to fail?

Possible metrics:

Metric	Meaning
Exit rate	How many businesses leave the industry
Insolvency rate	How many companies collapse
Volatility	How unstable profits/sales are
Cost pressure	Wages, rent, supplies, interest rates
Regulation risk	Licensing, compliance, safety rules
Discretionary exposure	Whether customers can easily cut spending

This is very important. A category can be popular but risky.

For example:

Restaurants/cafes: strong demand but high rent, labour, food cost, competition.
Construction: can have demand but high insolvency and cash-flow risk.
Cleaning: lower barrier to entry, but lower capital risk and recurring demand.
Health/aged care/NDIS: strong demand, but compliance-heavy.

ASIC insolvency data should be used as a negative risk signal.

Criteria 4: Competition and saturation

This answers:

Is the market already too crowded?

Possible metrics:

Metric	Meaning
Businesses per 10,000 residents	Local competition density
Listings for sale per category	Supply of sellers
Entry rate	Whether many new competitors are entering
Search demand vs business count	Demand/supply gap
Google Maps/Places count	Local competitor count
SEEK listing age	If many listings stay unsold, demand may be weak

High competition is not always bad. It can mean strong demand. But we need to compare demand versus supply.

Example:

A suburb with 40 cafes and slow population growth may be saturated.

A fast-growing suburb with few childcare, cleaning, fitness, or pet-care services may be more attractive.

Criteria 5: Capital requirement and buyer feasibility

This answers:

Can the buyer actually afford and operate this business?

Possible metrics:

Metric	Meaning
Asking price	Upfront acquisition cost
Working capital needed	Cash needed after purchase
Franchise fee	Initial franchise cost
Fit-out/equipment cost	Extra capital needed
Stock/SAV	Stock at valuation
Skill requirement	Does buyer need a license or industry experience?
Staff dependency	Can owner operate directly?
Financing difficulty	Is the business financeable?

This matters because a “good” business is not good for everyone.

Example:

A $1.5M childcare centre may be profitable but not suitable for a buyer with $100k budget.
A mobile cleaning or detailing business may be lower return but much more accessible.
A cafe may look affordable but need extra working capital and owner-operator skill.
Criteria 6: Listing quality / deal quality

This applies when scoring actual SEEK Business listings.

Possible metrics:

Metric	Good signal	Bad signal
Asking price vs profit	Low multiple	Very high multiple
Revenue disclosed	Transparent	No numbers
Profit disclosed	Transparent	Vague “huge potential”
Reason for sale	Clear	Missing or suspicious
Years established	Longer is safer	Very new
Staff/processes	Runs without owner	Owner-dependent
Lease terms	Long and stable	Short lease / high rent
Seller/broker quality	Reputable broker	Little seller info
Listing age	Fresh or fairly priced	Stale for months
Price changes	Reasonable	Repeated drops

This is where scraped marketplace data becomes useful.

4. Recommended scoring model

I would create a Business Opportunity Score from 0 to 100.

Suggested weights:

Component	Weight
Profitability	25%
Demand growth	20%
Risk / failure rate	20%
Competition saturation	15%
Capital feasibility	10%
Listing/deal quality	10%

Formula:

Business Score =
  0.25 * Profitability Score
+ 0.20 * Demand Score
+ 0.20 * Risk Score
+ 0.15 * Competition Score
+ 0.10 * Capital Fit Score
+ 0.10 * Listing Quality Score

Important: Risk Score should be inverted.

Meaning:

High insolvency risk = low score
Low insolvency risk = high score
5. Example scoring logic

Let’s say we compare four business categories:

Category	Profitability	Demand	Risk	Competition	Capital fit	Overall interpretation
Commercial cleaning	Medium	High	Low-medium	High	Good	Strong practical small-business candidate
Cafe / restaurant	Low-medium	High	High	High	Medium	Popular but risky
Pilates / fitness studio	High	Medium-high	Medium	Medium	Medium	Good if location and operator fit are strong
NDIS services	High	High	Medium-high compliance risk	Medium	Medium	Attractive but compliance-heavy
Online retail	Medium	Medium-high	Medium	Very high	Good	Good only with niche/product advantage
Construction trade business	Medium-high	High	High	Medium	Medium	Can be profitable but cash-flow risk is high

The key is that we should not just say “cafes are popular, recommend cafes.” We should say:

Cafes have demand, but their risk score is weak because of labour, rent, food costs, and insolvency exposure. Recommend only if the listing has strong verified financials, good lease terms, and high foot traffic.

6. Normalize all data into comparable scores

Different data sources use different units, so we need to normalize.

Example:

Profit margin:
0% margin = score 0
30%+ margin = score 100

Business exit rate:
25%+ exit rate = score 0
5% exit rate = score 100

Population growth:
Negative growth = score 0
3%+ annual growth = score 100

Competition density:
Very high businesses per capita = lower score
Moderate competition + high demand = higher score

A simple normalization function:

score = (value - min_value) / (max_value - min_value) * 100

For negative indicators like insolvency:

risk_score = 100 - normalized_insolvency_score
7. Create “hard filters” before scoring

Before calculating the final score, apply filters.

For example:

Exclude business if:
- Asking price > buyer budget
- Required license not matched by buyer
- Location not within target area
- Industry is too regulated for buyer profile
- No financial data disclosed
- Listing has unrealistic profit claims
- Business is too owner-dependent

This prevents recommending technically profitable but unsuitable businesses.

Example:

A dental clinic may be profitable, but if the buyer is not a dentist and cannot operate/manage one, it should be filtered out or marked as “requires specialist operator.”

8. Use two different scores: category score and listing score

This is important.

A. Category score

This is for business type.

Example:

Commercial Cleaning in Queensland: 82/100
Cafe in Sydney CBD: 51/100
Pilates Studio in Melbourne Inner East: 76/100

Uses:

ABS industry data
ATO benchmarks
ASIC insolvency
population growth
spending data
competition density
B. Listing score

This is for an actual SEEK Business listing.

Example:

Listing: "Profitable Commercial Cleaning Business Brisbane"
Score: 84/100

Uses:

Asking price
Claimed profit
Multiple
Years established
lease/contract details
staff structure
broker quality
listing age
description quality
category score

Suggested formula:

Listing Score =
  0.60 * Category Score
+ 0.40 * Deal Quality Score

This means even if the category is attractive, a bad listing can still score poorly.

9. Suggested data model
industry_scores
Field	Description
industry_code	ANZSIC/industry identifier
industry_name	Business category
profit_margin_score	Profitability score
demand_score	Demand score
risk_score	Failure/insolvency risk score
competition_score	Saturation score
capital_intensity_score	Lower capital requirement = higher score
final_category_score	Weighted category score
locations
Field	Description
location_id	LGA/suburb/state
population_growth	Local growth
median_income	Local buying power
business_density	Competition
household_spending_index	Demand proxy
opportunity_score	Location attractiveness
seek_listings
Field	Description
listing_id	SEEK listing ID
title	Listing title
category	Business category
location	Location
asking_price	Asking price
revenue	If disclosed
profit	If disclosed
profit_multiple	Asking price / annual profit
broker	Broker/seller
date_listed	Listing date
listing_age_days	Days active
description_quality_score	Transparency score
deal_quality_score	Listing-specific score
final_listing_score	Final recommendation score
10. Example recommendation labels

Instead of only showing a number, show human-readable labels.

Score	Label	Meaning
85–100	Strong recommendation	Good demand, profit, and risk profile
70–84	Worth investigating	Promising but needs due diligence
55–69	Caution	Some good signs, but several risks
40–54	Weak recommendation	Only suitable for specific buyers
0–39	Avoid / high risk	Poor fit or high failure risk

Example output:

Commercial Cleaning — Brisbane
Score: 82/100
Label: Worth investigating

Why:
- Stable B2B demand
- Lower capital requirement
- Recurring revenue potential
- Moderate competition
- Lower operational complexity than hospitality

Risks:
- Easy to enter, so competition can be high
- Labour quality and client retention matter
11. Important: “profitable” should not mean only “highest margin”

A common mistake would be ranking like this:

Highest profit margin = best business

That is wrong.

Some high-margin industries are not realistic for most buyers. IBISWorld lists superannuation-related industries as some of the highest-margin industries in Australia, but those are not practical recommendations for someone browsing SEEK Business to buy a small business.

So we need a realistic buyer filter.

Better definition:

A recommended business is one that has:
1. Evidence of profitability,
2. Evidence of demand,
3. Manageable risk,
4. Reasonable competition,
5. Realistic capital requirements,
6. Good buyer fit,
7. Transparent listing data.
12. Good candidate categories to test first

Based on the logic above, I would initially test these categories:

Category	Why it is worth testing
Commercial cleaning	Recurring demand, lower capital, B2B contracts
Property maintenance / gardening	Local recurring demand, ageing population, home services
NDIS / care services	Strong demand, but compliance-heavy
Fitness / Pilates studios	Potentially good margins, but location-sensitive
Mobile services	Lower rent exposure
Laundromats	Recurring local demand, semi-passive potential, but capital/equipment-heavy
Pet services	Growing lifestyle category, location-sensitive
Specialist trade services	Demand can be strong, but skill/operator dependent
Online niche retail	Scalable, but highly competitive
Bookkeeping / admin services	Low capital, but skill and trust-based

I would be more cautious with:

Category	Why caution is needed
Cafes/restaurants	High demand but high failure risk, labour/rent pressure
Construction businesses	Cash-flow and insolvency risk
Generic retail stores	Competition from ecommerce and large chains
Convenience stores	Thin margins, long hours, rent exposure
Tourism businesses	Seasonal and macro-sensitive
Beauty salons	Competitive and staff-dependent
13. MVP algorithm

For the first version, keep it simple.

Step 1: Collect SEEK Business listings.
Step 2: Classify each listing into a standard category.
Step 3: Enrich category with ABS/ATO/ASIC data.
Step 4: Enrich location with ABS population/income/business density data.
Step 5: Extract listing-level signals: price, location, age, financial claims, broker, description quality.
Step 6: Score category attractiveness.
Step 7: Score listing quality.
Step 8: Generate recommendation explanation.

Pseudo-code:

def score_business_listing(listing, buyer_profile):
    category = classify_category(listing)
    location = normalize_location(listing.location)

    profitability = get_profitability_score(category)
    demand = get_demand_score(category, location)
    risk = get_risk_score(category, location)
    competition = get_competition_score(category, location)
    capital_fit = get_capital_fit_score(listing, buyer_profile)
    listing_quality = get_listing_quality_score(listing)

    category_score = (
        0.25 * profitability +
        0.20 * demand +
        0.20 * risk +
        0.15 * competition +
        0.10 * capital_fit +
        0.10 * listing_quality
    )

    if listing.asking_price > buyer_profile.max_budget:
        category_score -= 25

    if listing.financials_missing:
        category_score -= 10

    if category.requires_license and not buyer_profile.has_license:
        category_score -= 20

    return clamp(category_score, 0, 100)
14. Recommendation explanation template

Every recommendation should explain why.

Example:

Recommended: Commercial Cleaning Business in Brisbane
Score: 82/100

Why it ranks well:
- Recurring B2B demand
- Lower upfront capital compared with hospitality
- Less rent exposure
- Good fit for owner-operator buyers
- Demand supported by business growth in the area

Main risks:
- Competitive market
- Staff reliability matters
- Contracts must be verified
- Revenue concentration risk if one client contributes too much

This is important because a user should not trust a black-box score.

15. My recommended criteria definition

For your system, define a “good business opportunity” like this:

A good business opportunity is a business category or listing that shows evidence of sustainable profit, growing or stable demand, acceptable failure risk, manageable competition, reasonable capital requirements, and strong fit with the buyer’s budget, location, skills, and risk tolerance.

Then use this scoring breakdown:

Criteria	Weight	Description
Profitability	25%	Margins, EBITDA, profit growth, cost ratios
Demand	20%	Spending, population, search interest, category growth
Risk	20%	Exit rate, insolvency, volatility, regulation
Competition	15%	Business density, listings, saturation
Capital fit	10%	Asking price, working capital, franchise fee
Listing quality	10%	Transparency, history, financials, seller quality

That gives you a practical, explainable recommendation engine instead of just a basic “sort by profit margin” tool.