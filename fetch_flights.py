import os, json, time, datetime as dt, urllib.request, urllib.parse, urllib.error
from pathlib import Path

ROOT=Path(__file__).parent
DATA=ROOT/'data'/'flights.json'
BASE='https://api.amadeus.com' if os.getenv('AMADEUS_ENV','test').lower()=='production' else 'https://test.api.amadeus.com'
TODAY=dt.date.today()

def request(url, data=None, token=None):
    headers={'Accept':'application/json'}
    if data is not None: headers['Content-Type']='application/x-www-form-urlencoded'
    if token: headers['Authorization']='Bearer '+token
    req=urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=35) as response: return json.load(response)

def main():
    key=os.environ.get('AMADEUS_CLIENT_ID'); secret=os.environ.get('AMADEUS_CLIENT_SECRET')
    if not key or not secret: raise SystemExit('Set AMADEUS_CLIENT_ID and AMADEUS_CLIENT_SECRET. Existing data remains unchanged.')
    auth=request(BASE+'/v1/security/oauth2/token',urllib.parse.urlencode({'grant_type':'client_credentials','client_id':key,'client_secret':secret}).encode())
    token=auth['access_token']
    # Spread departures over next 90 days. Four durations cover 2-5 inclusive calendar dates.
    # Keep request volume reasonable for API quotas; adjust SEARCH_STEP_DAYS as needed.
    step=max(1,int(os.getenv('SEARCH_STEP_DAYS','7')))
    departures=[TODAY+dt.timedelta(days=d) for d in range(7,91,step)]
    results=[]; errors=[]
    for departure in departures:
        for nights in (1,2,3,4):
            ret=departure+dt.timedelta(days=nights)
            params={'originLocationCode':'SEA','destinationLocationCode':'CPH','departureDate':departure.isoformat(),'returnDate':ret.isoformat(),'adults':1,'travelClass':'ECONOMY','currencyCode':'USD','max':5}
            try:
                payload=request(BASE+'/v2/shopping/flight-offers?'+urllib.parse.urlencode(params),token=token)
                for offer in payload.get('data',[]):
                    price=offer.get('price',{}); total=price.get('grandTotal') or price.get('total')
                    if total is None: continue
                    itineraries=offer.get('itineraries',[])
                    segments=[seg for itinerary in itineraries for seg in itinerary.get('segments',[])]
                    carriers=sorted({s.get('carrierCode','') for s in segments if s.get('carrierCode')})
                    stops=[max(0,len(i.get('segments',[]))-1) for i in itineraries]
                    results.append({'departure':departure.isoformat(),'return':ret.isoformat(),'calendar_days':nights+1,'price_usd':float(total),'carriers':carriers,'stops_each_way':stops,'source':'Amadeus Flight Offers Search','offer_id':offer.get('id'),'search_url':'https://www.google.com/travel/flights?hl=en&q='+urllib.parse.quote(f'round trip flights SEA to CPH {departure.isoformat()} to {ret.isoformat()}')})
            except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError,ValueError) as e:
                errors.append(f'{departure}/{ret}: {str(e)[:140]}')
            time.sleep(.12)
    # Avoid publishing a misleading empty refresh after a complete outage.
    if errors and not results: raise SystemExit('No valid fares fetched; preserving prior snapshot. Errors: '+'; '.join(errors[:3]))
    results.sort(key=lambda x:(x['price_usd'],x['departure']))
    previous={}
    if DATA.exists():
        try: previous=json.loads(DATA.read_text())
        except (ValueError,OSError): pass
    history=previous.get('history',[])
    if results: history.append({'date':TODAY.isoformat(),'lowest_usd':results[0]['price_usd']})
    history=history[-180:]
    output={'updated_at':dt.datetime.now(dt.timezone.utc).isoformat(),'provider':'Amadeus','environment':os.getenv('AMADEUS_ENV','test').lower(),'departure':'SEA','destination':'CPH','max_calendar_days':5,'budget_usd':500,'searched_departures':len(departures),'requests_attempted':len(departures)*4,'errors_count':len(errors),'offers':results[:300],'history':history,'note':'Flight prices are indicative and can change before booking. Test API may contain non-live sample fares.'}
    DATA.parent.mkdir(exist_ok=True)
    DATA.write_text(json.dumps(output,indent=2)+'\n')
    print(f'Published {len(results)} offers; {len(errors)} search errors')

if __name__=='__main__': main()
