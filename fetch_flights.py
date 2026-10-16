
import os
import json
import datetime as dt
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "data" / "flights.json"
TODAY = dt.datetime.now(dt.timezone.utc).date()

def get_flights(api_key, departure, return_date):
    params = {
        "engine": "google_flights",
        "departure_id": "SEA",
        "arrival_id": "CPH",
        "outbound_date": departure,
        "return_date": return_date,
        "type": "1",
        "adults": "1",
        "travel_class": "1",
        "currency": "USD",
        "hl": "en",
        "api_key": api_key
    }

    url = "https://serpapi.com/search.json?" + urllib.parse.urlencode(params)

    with urllib.request.urlopen(url, timeout=60) as response:
        return json.load(response)

def main():
    api_key = os.environ.get("SERPAPI_API_KEY")

    if not api_key:
        raise SystemExit("SERPAPI_API_KEY is missing.")

    # Rotate seven searches daily to stay under 250/month.
    # Each trip lasts 2 to 5 calendar days.
    combinations = []

    for days_ahead in range(7, 91, 7):
        for duration in (1, 2, 3, 4):
            combinations.append((days_ahead, duration))

    start = (TODAY.toordinal() * 7) % len(combinations)
    selected = [
        combinations[(start + i) % len(combinations)]
        for i in range(7)
    ]

    results = []
    errors = []

    for days_ahead, duration in selected:
        departure = TODAY + dt.timedelta(days=days_ahead)
        return_date = departure + dt.timedelta(days=duration)

        try:
            data = get_flights(
                api_key,
                departure.isoformat(),
                return_date.isoformat()
            )

            if "error" in data:
                raise ValueError(str(data["error"]))

            flights = data.get("best_flights", []) + data.get("other_flights", [])

            for offer in flights:
                price = offer.get("price")

                if price is None:
                    continue

                legs = offer.get("flights", [])
                airlines = sorted({
                    leg.get("airline")
                    for leg in legs
                    if leg.get("airline")
                })

                results.append({
                    "departure": departure.isoformat(),
                    "return": return_date.isoformat(),
                    "calendar_days": duration + 1,
                    "price_usd": float(price),
                    "carriers": airlines,
                    "stops_each_way": [],
                    "source": "Google Flights via SerpApi",
                    "search_url": (
                        "https://www.google.com/travel/flights?hl=en&q="
                        + urllib.parse.quote(
                            f"round trip SEA CPH "
                            f"{departure.isoformat()} "
                            f"{return_date.isoformat()}"
                        )
                    )
                })

        except (urllib.error.URLError, TimeoutError, ValueError) as error:
            errors.append(str(error)[:200])

    if not results:
        raise SystemExit(
            "No fares returned. Previous data preserved. "
            + "; ".join(errors[:3])
        )

    results.sort(key=lambda item: item["price_usd"])

    previous = {}

    if DATA.exists():
        try:
            previous = json.loads(DATA.read_text())
        except (ValueError, OSError):
            pass

    history = previous.get("history", [])
    history.append({
        "date": TODAY.isoformat(),
        "lowest_usd": results[0]["price_usd"]
    })

    output = {
        "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "provider": "SerpApi Google Flights",
        "environment": "production",
        "departure": "SEA",
        "destination": "CPH",
        "max_calendar_days": 5,
        "budget_usd": 500,
        "searched_departures": len(selected),
        "requests_attempted": len(selected),
        "errors_count": len(errors),
        "offers": results[:300],
        "history": history[-180:],
        "note": (
            "Indicative round-trip prices from Google Flights. "
            "Prices can change before booking. "
            "Seven date combinations checked per day."
        )
    }

    DATA.parent.mkdir(parents=True, exist_ok=True)
    DATA.write_text(json.dumps(output, indent=2) + "\n")

    print(f"Saved {len(results)} flight offers.")

if __name__ == "__main__":
    main()
