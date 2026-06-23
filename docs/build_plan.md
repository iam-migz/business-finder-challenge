todos:
- [ ] db setup: sqlite
- [ ] scrapper setup
- [ ] ai setup



features:
- AI organizes data based on need and ranks them based on if its a good deal, return for investment

categories
- business for sale
- franchises
- 


recommendation score: 
reason:

MVP
Step 1: Collect SEEK Business listings.
Step 2: Classify each listing into a standard category.
Step 3: Enrich category with ABS/ATO/ASIC data.
Step 4: Enrich location with ABS population/income/business density data.
Step 5: Extract listing-level signals: price, location, age, financial claims, broker, description quality.
Step 6: Score category attractiveness.
Step 7: Score listing quality.
Step 8: Generate recommendation explanation.



AI setup, in the fastapi create a dedicated AI service that we can use in the endpoint later on

create an AI service to that we can use it to feed in data, make a dedicated service for it focus on establishing initial contact

- **In-App AI Integration:** Integrate the **AI logic of your application** using the API key we provide for our locally hosted model. The endpoint is **OpenAI-compatible** (served via LiteLLM), so you can connect using any OpenAI-compatible client/SDK.
  
  - **Connection details**
    - OPENAI_BASE_URL=https://receiving-spokesman-loop-korean.trycloudflare.com/v1
    - Your API key will delivered via Discord from Luke
    - Model will automatically be routed, so no need to set this. 

cloudflared tunnel has been updated https://martial-miracle-critical-history.trycloudflare.com/

