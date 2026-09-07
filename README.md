# Tempora — AI Weather Intelligence Platform

Live: **https://tempora-indol.vercel.app**
API: **https://tempora-api.onrender.com**

![Tempora dashboard](docs/screenshots/desktop-dashboard.png)

Tempora started as a normal weather app — search a city, see the forecast, save your favorites. What makes it more than that is the AI layer on top: instead of just showing you numbers, it can tell you whether now's a good time to go for a run, help you plan your day around the forecast, or compare two cities before a weekend trip. The AI never makes those calls on its own, though — every score and recommendation comes from a deterministic scoring engine I built first, and Gemini's job is only ever to explain what that engine already decided, in plain language.

I built this to go deeper than a typical portfolio CRUD app: real auth, a Postgres database in production, a proper deployment pipeline, and an AI integration that's actually grounded in real data instead of just wrapping a chatbot around an API call.

## What it does

The core app is a fairly complete weather dashboard — current conditions, an hourly strip, a 5-day forecast, UV and air quality, unit toggling, light/dark themes. If you sign up, you can save favorite cities and it remembers your recent searches. Nothing unusual there, but it's solid: tested down to 375px-wide phones, keyboard-accessible modals, and it handles failure states honestly instead of just breaking.

The interesting part is the **Tempora AI** panel, which sits behind one button next to the weather card and opens into six tabs:

- **Chat** — ask it anything about the current city's weather. It re-fetches live data before answering, so it's never working off stale numbers.
- **Explain** — a plain-language read on current conditions, shown next to the actual 0–100 suitability score it's describing.
- **Activities** — pick from ten activities (running, beach, photography, university, and so on) and it finds the best time window today, each with its own comfort profile. This one actually caught a real bug during testing — it was originally happy to recommend a 3am picnic because the weather math looked good then, so I added a time-of-day constraint on top of the scoring.
- **Plan** — describe your day in your own words ("uni at 9, lunch at 1, gym in the evening") and it pulls out the events, matches each one to real hourly weather, and rates how comfortable each will be.
- **Compare** — put two cities side by side, optionally with a purpose ("weekend trip"), and it'll tell you which one's actually better right now.
- **Travel** — a multi-day trip brief with a recommended best day and packing suggestions. If you ask about dates further out than Open-Meteo's forecast actually covers, it says so plainly instead of guessing at future weather.

There's a seventh one too — a "Your Cities Today" button in the sidebar next to your favorites, which gives you a one-line AI comparison across everywhere you've saved.

## Why the AI never invents numbers

This was the thing I cared most about getting right. Every AI feature follows the same rule: the backend computes real numbers first — a suitability score, a best time window, a comparison — using plain deterministic Python, and Gemini is only ever handed those numbers and asked to explain them in a sentence or two. It's told explicitly, in every prompt, to say when something wasn't provided rather than make it up, and I tested that directly — asking for a trip two months out returns an honest "no forecast data available" instead of the model hallucinating a forecast for a date nobody can actually predict yet.

## Architecture

```
Browser (Vercel, plain HTML/CSS/JS — no framework)
        │
        ▼
FastAPI (Render)
   ├── SQLAlchemy → PostgreSQL (Neon)
   ├── httpx → Open-Meteo (weather, geocoding, air quality)
   └── Weather scoring engine (pure Python) → Gemini (explains the score, never computes it)
```

More detail on how each piece fits together, including a few of the trickier bugs I ran into, is in [ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Stack

**Backend** — FastAPI, SQLAlchemy 2.0, PostgreSQL via `psycopg`, JWT auth (`python-jose`), bcrypt password hashing, `httpx`, `pytest`.

**Frontend** — vanilla HTML/CSS/JS. No React, no build step. The whole color theme runs off a handful of CSS custom properties, so switching the palette is a one-file edit.

**AI** — Google Gemini, called directly over REST rather than through the SDK, with the model name kept in an environment variable so swapping it doesn't touch any feature code. That flexibility turned out to matter — I hit a couple of real, current Gemini quirks while building this (see below).

**Hosting** — Vercel for the frontend, Render for the API, Neon for Postgres.

## A couple of things I actually ran into

Worth mentioning because they weren't obvious going in:

- Gemini's newer API keys (the `AQ.`-prefixed "Auth key" format) need to be sent as an `x-goog-api-key` header, not the old `?key=` query parameter most tutorials still show.
- Gemini 3.x models spend part of their output token budget on internal "thinking" before writing anything visible, which silently truncated my first few responses until I explicitly set `thinkingLevel: "minimal"` for these short, factual answers.
- Different Gemini model tiers have very different free daily quotas — I found this out the hard way mid-build (20 requests/day on `gemini-3.6-flash` vs. much more headroom on the `-lite` variant), which is why the model is configurable rather than hardcoded.
- Neon's Postgres suspends itself when idle, which silently killed pooled connections until I added `pool_pre_ping=True` to the SQLAlchemy engine.

## Auth

Email/password, JWT stored client-side, bcrypt for hashing, 24-hour token expiry. I went back and forth on whether to use HttpOnly cookies instead — they'd close off the XSS-token-theft angle — but decided against it here: the frontend and backend live on different domains (Vercel and Render), so cookies would need `SameSite=None`, which reopens CSRF as a new problem to solve, and the app itself doesn't render any unsanitized user input that would make XSS a realistic risk in the first place. Bearer tokens felt like the more honest trade-off for this specific setup.

Every query that touches a user's favorites or recent searches is scoped to that user's ID — I checked this three separate ways over the course of building it: manually with two real accounts, and later with automated tests that specifically assert one account's data never shows up in another's response.

## Testing

There's a `pytest` suite covering the AI endpoints specifically — authentication, input validation, and (the one I actually cared about) user isolation. It mocks the Gemini call rather than hitting the real API, partly for speed and partly because the free-tier quota is thin enough that a test suite calling it for real would burn through it fast. Currently 17 tests, all passing, running in about a minute.

## Running it locally

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload
```

Serve `frontend/` with anything static (Live Server works fine). You'll need a `.env` in `backend/` — see `.env.example` for what it needs: a Postgres URL, a JWT secret, and a Gemini API key.

Run the tests with `pytest tests/ -v` from `backend/`.

## What's not finished

Being honest about what's still rough:

- Open-Meteo rate-limits per IP, and Render's free tier shares IPs across a lot of unrelated apps — so weather fetches can occasionally 503 for reasons that have nothing to do with Tempora itself. It fails cleanly when this happens rather than crashing, but it's a real limitation of stacking free-tier services on top of each other.
- City search takes the first geocoding match, so a city name that's shared by multiple places (there's no disambiguation UI) will sometimes resolve somewhere you didn't mean.
- No refresh tokens — sessions just expire after 24 hours and you log back in. Deliberate, to keep the token-theft window short without building out refresh infrastructure for a project this size.
- The weather intelligence engine already computes threshold-based alerts internally (high UV, poor air quality, and so on) but I haven't wired that up to an actual "alerts" feature yet — it's on the list.

## Screenshots

| | |
|---|---|
| ![Desktop](docs/screenshots/desktop-dashboard.png) | ![Mobile](docs/screenshots/mobile-dashboard.png) |
| ![Chat](docs/screenshots/tempora-ai-chat.png) | ![Activities](docs/screenshots/tempora-ai-activities.png) |
| ![Travel brief](docs/screenshots/tempora-ai-travel.png) | ![Favorite cities](docs/screenshots/favorite-cities-today.png) |

---

Built by Zunaira Zahid.
