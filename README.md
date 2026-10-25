# Yatra AI — Your India travel companion

A responsive travel-planning MVP based on the supplied blueprint. It includes a curated Jaipur knowledge pack, day-by-day itinerary generation, visible budget assumptions, source-linked local guide answers, and optional Sarvam chat integration. Browser speech recognition can dictate a guide question where supported.

## Run on Windows

1. Double-click `run.bat`. The first launch creates `.venv` and installs the Python dependencies.
2. Open `http://127.0.0.1:8000`.

Or activate a Python environment, install `requirements.txt`, then run `python -m uvicorn backend.main:app --reload` from this directory.

## Sarvam configuration

The provided key is stored in the local `.env` file and is excluded from Git. It is only read by the backend and sent to Sarvam's Chat Completion API; it is never included in frontend code. To replace the key, edit `.env`. `SARVAM_CHAT_MODEL` defaults to `sarvam-105b-conversations`. If the API is unreachable, the guide falls back to its curated note and source.

## MVP scope and data limits

- Jaipur is the only destination with a curated data pack. Other destinations are rejected clearly.
- Place notes link to official tourism, venue, or UNESCO sources. Verify visitor access, opening hours and prices with those sources.
- Ticket prices, transport gaps, intercity fares and budget amounts are illustrative assumptions, not live quotes or route calculations.
- No booking, payment, saved profile, live weather, or live route integration yet.
- Browser voice input depends on browser support and microphone permissions. Sarvam speech transcription and spoken playback can be added as the next phase.

## Structure

- `backend/main.py` — FastAPI endpoints, curated place data, itinerary and budget logic, Sarvam guide call
- `frontend/` — responsive single-page app
- `.env.example` — credential template
