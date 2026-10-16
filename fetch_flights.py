import os, json, datetime as dt, urllib.request, urllib.parse, urllib.error
from pathlib import Path

ROOT=Path(__file__).parent
DATA=ROOT/"data"/"flights.json"
TODAY=dt.datetime.now(dt.timezone.utc).date()
# Rotating destinations: broad coverage without claiming every airport was checked.
AIRPORTS=["LAX","SFO","LAS","JFK","MIA","HNL","ORD","DEN","BOS","YVR","YYZ","MEX","CUN","LHR","CDG","AMS","FCO","MAD","BCN","LIS","CPH","KEF","DUB","FRA","ZRH","IST","ATH","NRT","HND","ICN","TPE","BKK","SIN","MNL","SYD","AKL","DXB","DEL","LIM","BOG","SJO","GUA"]
def search(key, destination, departure, returning):
    params={"engine":"google_flights","departure_id":"SEA","arrival_id":destination,"outbound_date":departure,"return_date":returning,"type":"1","adults":"1","travel_class":"1","currency":"USD","hl":"en","api_key":key}
    with urllib.request.urlopen("https://serpapi.com/search.json?"+urllib.parse.urlencode(params),timeout=60) as response:
        return json.load(response)

def search_aviasales(token, destination):
    params={"origin":"SEA","destination":destination,"currency":"usd","token":token}
    url="https://api.travelpayouts.com/aviasales/v3/prices_for_dates?"+urllib.parse.urlencode(params)
    req=urllib.request.Request(url,headers={"Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=30) as response:
        return json.load(response)

def main():
    key=os.environ.get("SERPAPI_API_KEY")
    if not key: raise SystemExit("SERPAPI_API_KEY is missing")
    previous={}
    if DATA.exists():
        try: previous=json.loads(DATA.read_text())
        except (ValueError,OSError): pass
    # 7 requests/day (at most 217 per 31-day month), one destination per request.
    start=(TODAY.toordinal()*7)%len(AIRPORTS)
    destinations=[AIRPORTS[(start+i)%len(AIRPORTS)] for i in range(7)]
    offers=[]; errors=[]
    travel_token=os.environ.get('TRAVELPAYOUTS_API_TOKEN','').strip()
    aviasales_count=0
    for i,airport in enumerate(destinations):
        depart=TODAY+dt.timedelta(days=14+((TODAY.toordinal()+i*9)%70))
        ret=depart+dt.timedelta(days=2+((TODAY.toordinal()+i)%6))
        try:
            response=search(key,airport,depart.isoformat(),ret.isoformat())
            if response.get("error"): raise ValueError(str(response["error"]))
            for item in response.get("best_flights",[])+response.get("other_flights",[]):
                if item.get("price") is None: continue
                airlines=sorted({f.get("airline") for f in item.get("flights",[]) if f.get("airline")})
                offers.append({"departure":depart.isoformat(),"return":ret.isoformat(),"destination":airport,"calendar_days":(ret-depart).days+1,"price_usd":float(item["price"]),"carriers":airlines,"source":"Google Flights via SerpApi","fare_status":"Indicative; verify full round-trip total","search_url":"https://www.google.com/travel/flights?hl=en&q="+urllib.parse.quote("round trip SEA "+airport+" "+depart.isoformat()+" "+ret.isoformat())})
            if travel_token:
                try:
                    av=search_aviasales(travel_token,airport)
                    if av.get("success") is False: raise ValueError(str(av.get("error") or "API rejected request"))
                    for item in av.get("data",[]):
                        price=item.get("price"); departure_date=str(item.get("departure_at") or "")[:10]
                        return_date=str(item.get("return_at") or "")[:10]
                        if not price or not departure_date or not return_date: continue
                        try:
                            days=(dt.date.fromisoformat(return_date)-dt.date.fromisoformat(departure_date)).days+1
                        except ValueError: continue
                        if days<2: continue
                        link=item.get("link") or ""
                        verify_url=("https://www.aviasales.com"+link) if link.startswith("/") else ("https://www.aviasales.com/search/SEA"+departure_date[8:10]+departure_date[5:7]+airport+return_date[8:10]+return_date[5:7]+"1")
                        offers.append({"departure":departure_date,"return":return_date,"destination":airport,"calendar_days":days,"price_usd":float(price),"carriers":[item["airline"]] if item.get("airline") else [],"source":"Aviasales via Travelpayouts (cached)","fare_status":"Cached price; verify round-trip total","search_url":verify_url})
                        aviasales_count+=1
                except (urllib.error.URLError,TimeoutError,ValueError,KeyError,TypeError) as exc:
                    errors.append("Aviasales "+airport+": "+str(exc)[:160])
        except (urllib.error.URLError,TimeoutError,ValueError) as exc:
            errors.append(airport+": "+str(exc)[:160])
    if not offers: raise SystemExit("No fares returned; previous data preserved. "+"; ".join(errors[:2]))
    offers.sort(key=lambda x:x["price_usd"])
    history=previous.get("history",[])
    history.append({"date":TODAY.isoformat(),"lowest_usd":offers[0]["price_usd"],"destination":offers[0]["destination"]})
    # Compare a destination with its previously recorded lowest fare.
    previous_lows=previous.get("lowest_by_destination",{}) if previous.get("destination")=="ANY" else {}
    lows=dict(previous_lows)
    alerts=[]
    for offer in offers:
        airport=offer["destination"]; price=offer["price_usd"]
        old=previous_lows.get(airport)
        if old is not None and price<old:
            alerts.append({"destination":airport,"previous_usd":old,"current_usd":price,"departure":offer["departure"],"return":offer["return"],"search_url":offer["search_url"]})
        lows[airport]=min(price,lows.get(airport,float("inf")))
    output={"updated_at":dt.datetime.now(dt.timezone.utc).isoformat(),"provider":"Google Flights via SerpApi; Aviasales via Travelpayouts" if travel_token else "SerpApi Google Flights","environment":"production","departure":"SEA","destination":"ANY","trip_type":"round-trip","budget_usd":None,"searched_destinations":destinations,"requests_attempted":7,"errors_count":len(errors),"offers":offers[:200],"history":history[-180:],"lowest_by_destination":lows,"alerts":alerts[:30],"note":"Seven rotating destinations checked daily. Google Flights fares are indicative; Aviasales fares are cached. Verify complete round-trip totals before booking. Other destinations were not checked today.","aviasales_offers":aviasales_count}
    DATA.parent.mkdir(parents=True,exist_ok=True)
    DATA.write_text(json.dumps(output,indent=2)+"\n")
    print("Aviasales cached offers: "+str(aviasales_count))
    print("Saved "+str(len(offers))+" offers across "+str(len(destinations))+" destinations; "+str(len(alerts))+" price-drop alerts.")
if __name__=="__main__":main()
