# SEA → CPH Automatic Flight Price Tracker

A deployable website that displays **automatically updated round-trip airfare snapshots** for Seattle (SEA) to Copenhagen (CPH), with flexible departure dates, up to **5 calendar days including both departure and return dates**, and a **$500 USD target**.

## Publish the website and enable automatic updates

1. Create a GitHub repository and upload all files and folders in this ZIP, including `.github/workflows/daily.yml`.
2. Create an Amadeus for Developers account at https://developers.amadeus.com/ and create an application with **Flight Offers Search** API access. Note that test credentials/data are not guaranteed to reflect live fares. Real fare searching requires appropriate **production** access, which may have eligibility requirements, quotas, or costs.
3. In GitHub repository **Settings → Secrets and variables → Actions**, add repository secrets `AMADEUS_CLIENT_ID` and `AMADEUS_CLIENT_SECRET`. Never put secrets in HTML or commit them.
4. In the same page, add a repository variable `AMADEUS_ENV` set to `production` once production credentials are active. Use `test` only to test the integration, not to make buying decisions.
5. Under **Settings → Pages**, set **Source: GitHub Actions**. Ensure Actions workflows are enabled. Under **Actions → Daily SEA CPH fare update**, click **Run workflow** for the first update. The site will appear at `https://YOUR-USERNAME.github.io/YOUR-REPOSITORY/` once Pages deployment succeeds.
6. The workflow checks prices daily at **15:00 UTC** (8 AM Pacific daylight time / 7 AM Pacific standard time), stores snapshots in `data/flights.json`, and deploys the updated site. GitHub scheduled jobs may be delayed; they are not guaranteed to execute at an exact time.

## Data sources and limitations

- **Automatic price data:** Amadeus Flight Offers Search API, when properly configured. The script queries approximately 52 combinations (13 departures × 4 durations), covering departures roughly every 7 days over the next 90 days. It does **not** search every possible date; reducing `SEARCH_STEP_DAYS` increases API usage and costs.
- **Comparison links only:** RatePunk, Google Flights, Skyscanner, KAYAK, Momondo, Expedia. No prices are scraped from these sites. Some linked sites may redirect or require dates to be entered.
- **Price:** `grandTotal` or `total` returned by Amadeus, in USD, for one adult economy traveler; baggage, card fees, or other add-ons may be extra. Offers may expire or change before booking.
- **Dates:** calendar-day difference of 1–4 days (2–5 inclusive dates). Long overnight flights may leave little time at the destination.
- **Notifications:** the separate ChatGPT daily flight alert already created is not connected to this website. This repository does not send email or push alerts. Add a mail provider/API for website-triggered alerts.
- **Availability:** A successful API request may still return no offers. The script preserves the last snapshot on complete failure.

## Local preview

Run `python -m http.server 8000` in the project directory and open `http://localhost:8000`. The dashboard will initially show no prices until the API update runs.

## Adjusting searches

`SEARCH_STEP_DAYS=7` by default. Use `3` or `1` for more thorough searches, subject to API quota. Script `fetch_flights.py` contains date range and duration controls. The search uses future dates, so it stays current.
