from __future__ import annotations
import json, os, urllib.error, urllib.request, urllib.parse
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env')
except ImportError:
    pass

app = FastAPI(title='Yatra AI', version='0.2.0')

# Curated, source-linked knowledge packs, one per destination.
DESTINATIONS = json.loads((ROOT / 'backend' / 'destinations.json').read_text(encoding='utf-8'))


def _lookup(name: str):
    """Case-insensitive destination lookup. Returns (canonical_name, data) or (None, None)."""
    if not name:
        return None, None
    for k, v in DESTINATIONS.items():
        if k.lower() == name.strip().lower():
            return k, v
    return None, None


class Plan(BaseModel):
    destination: str = Field('Jaipur', min_length=2, max_length=80)
    start_city: str = 'Delhi'
    days: int = Field(3, ge=1, le=7)
    travelers: int = Field(2, ge=1, le=20)
    budget: int = Field(30000, ge=1000)
    interests: list[str] = Field(default_factory=lambda: ['Heritage'])
    pace: Literal['Relaxed', 'Balanced', 'Packed'] = 'Balanced'
    language: str = 'English'
    travel_style: Literal['Budget', 'Comfort', 'Premium'] = 'Budget'


class Ask(BaseModel):
    place: str
    destination: str = 'Jaipur'
    mode: Literal['Quick facts', 'Story mode', 'Deep dive'] = 'Quick facts'
    language: str = 'English'
    question: str = 'Tell me about this place.'


@app.get('/api/health')
def health():
    return {'status': 'ok', 'sarvam_configured': bool(os.getenv('SARVAM_API_KEY')),
            'destinations': len(DESTINATIONS)}


@app.get('/api/destinations')
def destinations():
    return {'destinations': [{'name': k, 'places': [p['name'] for p in v['places']]}
                             for k, v in DESTINATIONS.items()]}


@app.get('/api/places')
def places(destination: str = 'Jaipur'):
    key, dest = _lookup(destination)
    if not dest:
        raise HTTPException(404, f"'{destination}' is not in the guide yet.")
    return {'destination': key, 'places': dest['places'],
            'disclaimer': 'Confirm current hours, access and ticket prices using official sources.'}


@app.post('/api/plan')
def plan(q: Plan):
    key, dest = _lookup(q.destination)
    if not dest:
        raise HTTPException(422, 'The guide currently covers: ' + ', '.join(DESTINATIONS) + '. Choose one of these.')
    places = dest['places']
    rank = {a: i for i, a in enumerate(dest['area_order'])}
    # Cluster stops by area; cap each day to preserve breaks and feasible daylight.
    selected = sorted(places, key=lambda p: (0 if any(i.lower() in (p['category'] + ' ' + p['name']).lower() for i in q.interests) else 1, rank.get(p['area'], 99)))
    max_stops = {'Relaxed': 3, 'Balanced': 4, 'Packed': 5}[q.pace]
    selected = selected[:min(len(selected), q.days * max_stops)]
    per = (len(selected) + q.days - 1) // q.days
    days = []
    for d in range(q.days):
        group = selected[d * per:(d + 1) * per]
        if not group:
            break
        minute = 9 * 60
        stops = []
        for i, p in enumerate(group):
            transfer = 35 if i else 0
            minute += transfer
            h, m = divmod(minute, 60)
            stops.append({**p, 'start': f"{h % 12 or 12}:{m:02d} {'AM' if h < 12 else 'PM'}", 'transit_minutes': transfer,
                          'map_url': 'https://www.google.com/maps/search/?api=1&query=' + urllib.parse.quote(p['name'] + ', ' + key)})
            minute += p['visit'] + 35
        days.append({'day': d + 1, 'theme': ' · '.join(dict.fromkeys(p['area'] for p in group)),
                     'stops': stops, 'validated': minute < 19 * 60})
    rates = {'Budget': (1800, 900, 550, 450), 'Comfort': (4500, 2200, 1100, 1000), 'Premium': (10000, 5500, 2200, 2200)}
    travel, stay, food, local = rates[q.travel_style]
    costs = {'Intercity travel': travel, 'Stay': q.days * stay, 'Food': q.days * food,
             'Attraction tickets': sum(p['ticket'] for day in days for p in day['stops']), 'Local transport': q.days * local}
    costs['Contingency'] = round(sum(costs.values()) * .12)
    per_person = sum(costs.values())
    return {'destination': key, 'days': days,
            'summary': {'travelers': q.travelers, 'start_city': q.start_city, 'pace': q.pace, 'language': q.language},
            'budget': {'items': costs, 'per_person': per_person, 'group_total': per_person * q.travelers,
                       'target': q.budget, 'within_budget': per_person * q.travelers <= q.budget,
                       'assumptions': 'Illustrative estimates, not live quotes. Varies by season, origin and choices.'},
            'notice': f'Curated {key} demo. Hours, prices, routes and intercity fares are not live verified. Check official sources before travel.'}


@app.post('/api/guide')
def guide(q: Ask):
    key, dest = _lookup(q.destination)
    if not dest:
        raise HTTPException(404, 'That destination is not in the guide yet.')
    p = next((x for x in dest['places'] if x['name'].lower() == q.place.lower()), None)
    if not p:
        raise HTTPException(404, f"That place is not in the {key} guide yet.")
    api_key = os.getenv('SARVAM_API_KEY')
    if api_key:
        prompt = f"You are a careful India travel guide. Explain {p['name']} in {q.language}, mode {q.mode}. Use only these grounded notes: {p['note']} Official reference: {p['source']}. Separate documented history from legends. Do not invent facts, prices or timings. If notes do not answer, say so. Traveler asks: {q.question}"
        body = json.dumps({'model': os.getenv('SARVAM_CHAT_MODEL', 'sarvam-105b-conversations'),
                           'messages': [{'role': 'user', 'content': prompt}], 'temperature': 0.3}).encode()
        req = urllib.request.Request('https://api.sarvam.ai/v1/chat/completions', data=body,
                                     headers={'api-subscription-key': api_key, 'Content-Type': 'application/json'}, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                data = json.loads(r.read())
            return {'place': p['name'], 'answer': data['choices'][0]['message']['content'], 'source': p['source'], 'powered_by': 'Sarvam AI'}
        except (urllib.error.URLError, KeyError, IndexError, TimeoutError):
            pass
    return {'place': p['name'], 'answer': f"{p['name']} — {p['note']} Check the official reference for current visitor information.",
            'source': p['source'], 'powered_by': 'Curated guide fallback'}


app.mount('/assets', StaticFiles(directory=ROOT / 'frontend' / 'assets'), name='assets')


@app.get('/{path:path}')
def frontend(path: str):
    return FileResponse(ROOT / 'frontend' / 'index.html')
