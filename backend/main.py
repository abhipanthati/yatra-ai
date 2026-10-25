from __future__ import annotations
import json, os, urllib.error, urllib.request, urllib.parse
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
ROOT=Path(__file__).resolve().parent.parent
try:
 from dotenv import load_dotenv
 load_dotenv(ROOT/'.env')
except ImportError: pass
app=FastAPI(title='Yatra AI',version='0.1.0')
PLACES=[
 {'name':'Amber Fort','area':'Amer','category':'Heritage','hours':'8:00 AM – 5:30 PM','visit':150,'ticket':200,'note':'Hilltop fort complex; allow time for ramparts and courtyards.','source':'https://www.tourism.rajasthan.gov.in/amber-fort.html'},
 {'name':'Hawa Mahal','area':'Old City','category':'Architecture','hours':'9:00 AM – 4:30 PM','visit':75,'ticket':50,'note':'The five-storey façade is best appreciated from the street and its museum.','source':'https://www.tourism.rajasthan.gov.in/hawa-mahal.html'},
 {'name':'City Palace','area':'Old City','category':'Heritage','hours':'9:30 AM – 5:00 PM','visit':120,'ticket':300,'note':'A living palace complex with museums and courtyards; access varies by ticket.','source':'https://citypalace.org/'},
 {'name':'Jantar Mantar','area':'Old City','category':'Culture','hours':'9:00 AM – 4:30 PM','visit':90,'ticket':50,'note':'An 18th-century astronomical observatory and UNESCO World Heritage site.','source':'https://whc.unesco.org/en/list/1338/'},
 {'name':'Jal Mahal viewpoint','area':'Man Sagar Lake','category':'Photography','hours':'Daylight','visit':35,'ticket':0,'note':'Lakeside viewpoint; palace interior is not generally open to visitors.','source':'https://www.tourism.rajasthan.gov.in/jaipur.html'},
 {'name':'Albert Hall Museum','area':'Ram Niwas Garden','category':'Museum','hours':'9:00 AM – 5:00 PM','visit':100,'ticket':40,'note':'A broad collection in an Indo-Saracenic landmark building.','source':'https://www.tourism.rajasthan.gov.in/albert-hall-museum.html'},
 {'name':'Patrika Gate','area':'Jawahar Circle','category':'Architecture','hours':'Daylight','visit':35,'ticket':0,'note':'Colourful public gateway often visited for photography.','source':'https://www.tourism.rajasthan.gov.in/jaipur.html'},
 {'name':'Bapu Bazaar','area':'Old City','category':'Food & shopping','hours':'Late morning – evening','visit':90,'ticket':0,'note':'Busy market for textiles, footwear and street snacks; shop hours vary.','source':'https://www.tourism.rajasthan.gov.in/jaipur.html'}]
class Plan(BaseModel):
 destination:str=Field('Jaipur',min_length=2,max_length=80); start_city:str='Delhi'; days:int=Field(3,ge=1,le=7); travelers:int=Field(2,ge=1,le=20); budget:int=Field(30000,ge=1000); interests:list[str]=Field(default_factory=lambda:['Heritage']); pace:Literal['Relaxed','Balanced','Packed']='Balanced'; language:str='English'; travel_style:Literal['Budget','Comfort','Premium']='Budget'
class Ask(BaseModel): place:str; mode:Literal['Quick facts','Story mode','Deep dive']='Quick facts'; language:str='English'; question:str='Tell me about this place.'
@app.get('/api/health')
def health(): return {'status':'ok','sarvam_configured':bool(os.getenv('SARVAM_API_KEY'))}
@app.get('/api/places')
def places(): return {'destination':'Jaipur','places':PLACES,'disclaimer':'Confirm current hours, access and ticket prices using official sources.'}
@app.post('/api/plan')
def plan(q:Plan):
 if 'jaipur' not in q.destination.lower(): raise HTTPException(422,'The MVP currently has a curated Jaipur knowledge pack. Choose Jaipur to generate a source-linked plan.')
 # Cluster stops by area; cap each day to preserve breaks and feasible daylight.
 order=['Amer','Man Sagar Lake','Old City','Ram Niwas Garden','Jawahar Circle']; rank={a:i for i,a in enumerate(order)}
 selected=sorted(PLACES,key=lambda p:(0 if any(i.lower() in (p['category']+' '+p['name']).lower() for i in q.interests) else 1,rank.get(p['area'],99)))
 max_stops={'Relaxed':3,'Balanced':4,'Packed':5}[q.pace]; selected=selected[:min(len(selected),q.days*max_stops)]; per=(len(selected)+q.days-1)//q.days; days=[]
 for d in range(q.days):
  group=selected[d*per:(d+1)*per]
  if not group: break
  minute=9*60; stops=[]
  for i,p in enumerate(group):
   transfer=35 if i else 0; minute+=transfer; h,m=divmod(minute,60)
   stops.append({**p,'start':f"{h%12 or 12}:{m:02d} {'AM' if h<12 else 'PM'}",'transit_minutes':transfer,'map_url':'https://www.google.com/maps/search/?api=1&query='+urllib.parse.quote(p['name']+', Jaipur')}); minute+=p['visit']+35
  days.append({'day':d+1,'theme':' · '.join(dict.fromkeys(p['area'] for p in group)),'stops':stops,'validated':minute<19*60})
 rates={'Budget':(1800,900,550,450),'Comfort':(4500,2200,1100,1000),'Premium':(10000,5500,2200,2200)}; travel,stay,food,local=rates[q.travel_style]
 costs={'Intercity travel':travel,'Stay':q.days*stay,'Food':q.days*food,'Attraction tickets':sum(p['ticket'] for day in days for p in day['stops']),'Local transport':q.days*local}; costs['Contingency']=round(sum(costs.values())*.12); per_person=sum(costs.values())
 return {'destination':q.destination,'days':days,'summary':{'travelers':q.travelers,'start_city':q.start_city,'pace':q.pace,'language':q.language},'budget':{'items':costs,'per_person':per_person,'group_total':per_person*q.travelers,'target':q.budget,'within_budget':per_person*q.travelers<=q.budget,'assumptions':'Illustrative estimates, not live quotes. Varies by season, origin and choices.'},'notice':'Curated Jaipur demo. Hours, prices, routes and intercity fares are not live verified. Check official sources before travel.'}
@app.post('/api/guide')
def guide(q:Ask):
 p=next((x for x in PLACES if x['name'].lower()==q.place.lower()),None)
 if not p: raise HTTPException(404,'That place is not in the Jaipur demo guide yet.')
 key=os.getenv('SARVAM_API_KEY')
 if key:
  prompt=f"You are a careful India travel guide. Explain {p['name']} in {q.language}, mode {q.mode}. Use only these grounded notes: {p['note']} Official reference: {p['source']}. Separate documented history from legends. Do not invent facts, prices or timings. If notes do not answer, say so. Traveler asks: {q.question}"
  body=json.dumps({'model':os.getenv('SARVAM_CHAT_MODEL','sarvam-105b-conversations'),'messages':[{'role':'user','content':prompt}],'temperature':0.3}).encode()
  req=urllib.request.Request('https://api.sarvam.ai/v1/chat/completions',data=body,headers={'api-subscription-key':key,'Content-Type':'application/json'},method='POST')
  try:
   with urllib.request.urlopen(req,timeout=25) as r: data=json.loads(r.read())
   return {'place':p['name'],'answer':data['choices'][0]['message']['content'],'source':p['source'],'powered_by':'Sarvam AI'}
  except (urllib.error.URLError,KeyError,IndexError,TimeoutError): pass
 return {'place':p['name'],'answer':f"{p['name']} — {p['note']} Check the official reference for current visitor information.",'source':p['source'],'powered_by':'Curated guide fallback'}
app.mount('/assets',StaticFiles(directory=ROOT/'frontend'/'assets'),name='assets')
@app.get('/{path:path}')
def frontend(path:str): return FileResponse(ROOT/'frontend'/'index.html')
