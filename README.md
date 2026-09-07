# Tempora — AI Weather Intelligence Platform

Tempora doesn't just tell you what the weather is — it helps you understand what it means for your day. It combines live weather data with a deterministic scoring engine and Google Gemini to answer questions like *"Should I go for a run?"*, *"Which of my saved cities is nicest today?"*, and *"Is this weekend good for a trip?"* — grounded entirely in real data, never invented.

**Live demo:** https://tempora-indol.vercel.app
**API:** https://tempora-api.onrender.com
**Backend repo root:** `backend/` · **Frontend repo root:** `frontend/`

![Tempora desktop dashboard](docs/screenshots/desktop-dashboard.png)

---

## Table of Contents

- [The Problem](#the-problem)
- [The Solution](#the-solution)
- [Features](#features)
- [AI Features](#ai-features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Weather Data](#weather-data)
- [Authentication & Authorization](#authentication--authorization)
- [Database](#database)
- [AI Architecture & Safety](#ai-architecture--safety)
- [Security](#security)
- [Testing](#testing)
- [Deployment](#deployment)
- [Environment Variables](#environment-variables)
- [Local Development](#local-development)
- [Screenshots](#screenshots)
- [Known Limitations](#known-limitations)
- [Roadmap](#roadmap)
- [Author](#author)

---

## The Problem

Most weather apps stop at numbers: temperature, humidity, a forecast grid. They leave the actual decision — *is this good weather for what I'm planning?* — entirely to the user. That gap is where Tempora lives.

## The Solution

Tempora pairs real weather data with a **deterministic suitability-scoring engine** (temperature, precipitation, wind, UV, and air quality, each scored transparently against activity-specific comfort ranges) and layers **Google Gemini** on top purely to *explain* those scores in plain language. The AI never invents a number — it only ever narrates values the backend has already computed from real Open-Meteo data.

## Features

**Core weather**
- Current conditions, 24-hour hourly strip, 5-day forecast
- UV Index and Air Quality Index (US AQI), with graceful degradation if AQI is temporarily unavailable
- °C/°F toggle, light/dark theme
- City search with recent-search history and favorites (authenticated)

**Accounts**
- Email/password registration and login (JWT, bcrypt-hashed passwords)
- Per-user favorites and recent searches, fully isolated between accounts
- Session expiry handled gracefully — an expired or invalid token prompts re-login instead of silently failing

**Responsive & accessible**
- Tested at 375px, 390px, 768px, and 1024px+ breakpoints
- Auth modal has a full keyboard focus trap, `Escape`-to-close, and `aria-live` error announcements

## AI Features

All AI features live behind a single **🤖 Tempora AI** panel, opened from the weather card, with six tabs:

| Tab | What it does |
|---|---|
| 💬 **Chat** | Ask any question about the current city's weather; answers are grounded in live, re-fetched data — never the client's cached numbers |
| 📋 **Explain** | Plain-language summary of current conditions, alongside the deterministic 0–100 Outdoor Suitability score it's explaining |
| 🏃 **Activities** | Pick from 10 activities (running, beach, photography, university, etc.); each has its own comfort profile and realistic time-of-day window, so a "best time" is never suggested outside hours the activity would actually happen |
| 📅 **Plan** | Describe your day in free text ("uni at 9, lunch at 1, gym in the evening") — Gemini extracts the events, then real hourly weather is matched to each one deterministically |
| ⚖️ **Compare** | Side-by-side live comparison of two cities, with an optional purpose (e.g. "weekend trip") the AI weighs the recommendation against |
| 📆 **Travel** | Multi-day trip brief with a best-day recommendation and packing suggestions. If requested dates fall outside Open-Meteo's forecast range, Tempora says so plainly rather than fabricating future weather |

A seventh capability, **📍 Your Cities Today**, lives in the sidebar next to Favorites — a one-click AI summary comparing conditions across all of a user's saved cities.

## Architecture

```
Browser (Vercel, static HTML/CSS/JS)
        │
        ▼
FastAPI (Render)
        │
        ├──▶ SQLAlchemy ──▶ PostgreSQL (Neon, serverless)
        │
        ├──▶ httpx ──▶ Open-Meteo (geocoding, forecast, air quality)
        │
        └──▶ Weather Intelligence Engine (pure Python, deterministic scoring)
                    │
                    ▼
              Gemini API (narration only — never computes scores itself)
```

## Tech Stack

**Backend:** FastAPI · SQLAlchemy 2.0 · PostgreSQL via `psycopg` 3 · `python-jose` (JWT) · `passlib`/bcrypt · `httpx` · `pytest` + `pytest-asyncio`

**Frontend:** Vanilla HTML/CSS/JavaScript, no framework or build step — CSS custom properties drive the entire theme (including light/dark mode) from a single set of variables

**AI:** Google Gemini API, called directly over REST (no SDK dependency), model configurable via an environment variable rather than hardcoded

**Infrastructure:** Neon (Postgres) · Render (API) · Vercel (static frontend)

## Weather Data

All weather data comes from [Open-Meteo](https://open-meteo.com/), a free, no-API-key weather service:
- Geocoding for city search
- Current conditions + daily UV
- 5-day and 48-hour hourly forecasts
- Air quality (US AQI)

Every numerical claim the AI makes is sourced from one of these calls — nothing is estimated or interpolated by the language model.

## Authentication & Authorization

JWT Bearer tokens, stored client-side and attached via `Authorization` headers. Passwords are hashed with bcrypt; tokens expire after 24 hours.

**Why not HttpOnly cookies?** Considered and deliberately not used: Tempora's frontend is a static SPA with no server-rendered pages and no unsanitized HTML injection points, so its practical XSS surface is low — while cross-origin cookies (Vercel ↔ Render are different domains) would require `SameSite=None` and reintroduce CSRF as a new, separate risk to defend against. Bearer-token auth was the better fit for this specific deployment shape.

Every authenticated query is scoped to `current_user.id` at the database layer — verified both manually (two real accounts, live cross-checking) and via automated tests (see [Testing](#testing)).

## Database

PostgreSQL, hosted on Neon (serverless — scales to zero when idle). Three tables: `users`, `favorites`, `recent_searches`, related by foreign key with cascading deletes. The connection uses `pool_pre_ping=True` specifically to handle Neon's automatic suspend/resume behavior transparently.

## AI Architecture & Safety

- **Provider abstraction** (`services/ai/provider.py`): a thin REST wrapper around Gemini, isolated so switching providers later doesn't touch any feature code
- **Context builder**: sends only the minimal, real weather fields a given feature needs — never a raw data dump
- **Rate limiting**: per-user per-minute cap plus a shared global daily cap, sized against Gemini's actual free-tier quota
- **Prompt rules enforced on every feature**: never invent a value not explicitly provided; state plainly when data is unavailable rather than guessing; no medical/safety authority claims
- **AI never computes** — activity scores, suitability ratings, and "best day" selections are all plain deterministic Python; the model only narrates results it's handed

## Security

- Bcrypt password hashing, JWT expiry, per-user data isolation (see Testing)
- CORS allowlist (no wildcard), configured per environment via `CORS_ORIGINS`
- Global error handling: unhandled exceptions are logged in full server-side but only ever return a generic, safe message to the client — full tracebacks never reach the browser
- AI output is inserted into the DOM via `textContent`/`createElement`, never `innerHTML` — even though prompt rules constrain the model's output, it's still treated as untrusted
- No secrets committed at any point (verified before every commit throughout development)

## Testing

17 automated backend tests (`pytest`) covering the AI layer specifically:
- Every AI endpoint rejects unauthenticated and invalid-token requests
- Input validation (empty messages, unknown activities/cities, malformed or illogical date ranges, oversized inputs)
- **User isolation, proven programmatically**: two independent test accounts, asserting one user's favorite-city data never appears in another's AI-generated summary

The real Gemini API is mocked in tests — this verifies Tempora's own logic (auth, validation, isolation) deterministically, without depending on or spending quota against a live third-party service.

```
17 passed in ~75s
```

## Deployment

| Layer | Provider | Notes |
|---|---|---|
| Frontend | Vercel | Static hosting, root directory `frontend/` |
| Backend | Render | Free-tier web service, root directory `backend/`, binds to Render's `$PORT` |
| Database | Neon | Serverless Postgres, `pool_pre_ping` enabled for cold-start resilience |

## Environment Variables

**Backend (`backend/.env`)**
```
DATABASE_URL=postgresql+psycopg://user:password@host/dbname?sslmode=require
JWT_SECRET=<random secret, e.g. python -c "import secrets; print(secrets.token_hex(32))">
GEMINI_API_KEY=<your Gemini API key>
AI_MODEL=gemini-3.5-flash-lite
CORS_ORIGINS=http://127.0.0.1:5500,https://your-vercel-domain.vercel.app
```

Frontend requires no environment variables — its API base URL is resolved in `frontend/js/config.js`, auto-detecting local development vs. production.

## Local Development

```powershell
# Backend
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload

# Frontend
# Serve frontend/ with any static server, e.g. VS Code Live Server
```

Run tests:
```powershell
cd backend
pytest tests/ -v
```

## Screenshots

| | |
|---|---|
| ![Desktop dashboard](docs/screenshots/desktop-dashboard.png) | ![Mobile dashboard](docs/screenshots/mobile-dashboard.png) |
| Desktop — Twilight theme | Mobile — responsive layout |
| ![Tempora AI - Chat](docs/screenshots/tempora-ai-chat.png) | ![Tempora AI - Activities](docs/screenshots/tempora-ai-activities.png) |
| Weather Copilot chat | Activity Advisor |
| ![Tempora AI - Travel Brief](docs/screenshots/tempora-ai-travel.png) | ![Favorite City Intelligence](docs/screenshots/favorite-cities-today.png) |
| Multi-day travel brief | Favorite City Intelligence |

## Known Limitations

- **Open-Meteo's per-IP rate limit** can occasionally cause temporary weather-fetch failures on shared free-tier hosting (Render's IP pool is shared across many unrelated apps). Tempora degrades gracefully — a clean, honest error message, never a crash — but this is a real constraint of the free-tier hosting stack, not something the app can fully control.
- **Gemini's free-tier daily quota varies by model generation** — confirmed directly against the live API during development, not assumed from documentation. Lighter model variants (`-flash-lite`) currently offer meaningfully more daily headroom than the full Flash model.
- Geocoding takes the first match only; ambiguous city names (e.g. common names shared across countries) aren't disambiguated in the UI.
- Sessions expire after 24 hours with no refresh-token mechanism — by design, to bound token-theft exposure on a portfolio-scale project without adding refresh-token infrastructure.

## Roadmap

- Weather alert explainer using deterministic threshold detection (already built in the scoring engine, not yet exposed as a feature)
- City name disambiguation in search
- Optional HttpOnly-cookie auth mode if the app's trust boundary changes

## Author

Built by Zunaira Zahid — a full-stack, AI-integrated weather intelligence platform combining FastAPI, PostgreSQL, deterministic scoring, and the Gemini API, deployed on Vercel, Render, and Neon.
