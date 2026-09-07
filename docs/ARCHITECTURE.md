# Tempora — Architecture

This document goes one level deeper than the README: what each layer does, why it's shaped the way it is, and the specific trade-offs behind each decision. Written to be defensible in a technical interview, not just descriptive.

---

## 1. System Overview

```
┌─────────────────────────────────────────────────────────────┐
│  Browser                                                     │
│  Vercel — static HTML/CSS/JS, no framework, no build step    │
└───────────────────────────┬───────────────────────────────────┘
                             │ fetch() — JWT Bearer auth
                             ▼
┌─────────────────────────────────────────────────────────────┐
│  FastAPI (Render)                                             │
│                                                                 │
│  ┌───────────┐  ┌────────────┐  ┌──────────────────────────┐ │
│  │  Routers   │  │  Services   │  │  Weather Intelligence     │ │
│  │  auth      │  │  weather_   │  │  Engine (pure Python,     │ │
│  │  favorites │  │  service    │  │  deterministic scoring)   │ │
│  │  recent_   │  │  ai/        │  └──────────────────────────┘ │
│  │  searches  │  │  provider   │                                │
│  │  ai        │  │  context    │                                │
│  └───────────┘  │  prompts    │                                │
│                  │  rate_      │                                │
│                  │  limiter    │                                │
│                  └────────────┘                                │
└──────┬───────────────────┬──────────────────────┬─────────────┘
       │                   │                       │
       ▼                   ▼                       ▼
┌─────────────┐   ┌─────────────────┐   ┌─────────────────────┐
│  PostgreSQL  │   │  Open-Meteo      │   │  Gemini API           │
│  (Neon)      │   │  (geocoding,     │   │  (narration only —   │
│  users,      │   │  forecast,       │   │  never computes a     │
│  favorites,  │   │  air quality)    │   │  score)               │
│  recent_     │   └─────────────────┘   └─────────────────────┘
│  searches    │
└─────────────┘
```

---

## 2. Request Lifecycle — a Weather Search

1. Frontend `fetch()`s `GET /weather?city=...` (no auth required — weather browsing is public; only favorites/recent-searches/AI require login).
2. `main.py` calls `resolve_city()` → Open-Meteo geocoding. On no match, raises `CityNotFoundError` → mapped to `404`.
3. `fetch_current_weather()` and `fetch_air_quality()` run — AQI failure is caught and degrades to `null` rather than failing the whole response (a deliberate design choice preserved from the original project).
4. All Open-Meteo calls route through a single shared `_get()` helper (`weather_service.py`) that distinguishes a `429`/`5xx` from Open-Meteo (→ `WeatherProviderError` → clean `503`) from a normal successful response — added specifically after a real rate-limit incident during production deployment (see Known Limitations in the README).
5. Response is validated against a Pydantic response model (`WeatherResponse`) before serialization — guarantees the frontend never receives a malformed shape.

## 3. Request Lifecycle — an AI Feature (e.g. Explain My Weather)

This is the clearest example of the project's core design principle: **AI explains, deterministic code decides.**

1. `get_current_user` dependency validates the JWT; a missing/expired/invalid token short-circuits to `401` before any other work happens.
2. `check_rate_limit(user_id)` — checked *before* any network call, so a rate-limited request never wastes an Open-Meteo or Gemini call.
3. Live weather is **re-fetched server-side** — the backend never trusts weather numbers the client might send, guaranteeing the AI only ever sees current, server-verified data.
4. `score_current_conditions()` (pure Python, `weather_intelligence.py`) computes a 0-100 suitability score from real values — temperature, wind, UV, AQI — using a shared linear-falloff formula with per-factor "ideal" bands.
5. The score, its component breakdown, and the real weather context are handed to `generate_text()`, which calls Gemini with a system prompt that explicitly forbids inventing or recalculating any value it's given.
6. The response returns **both** the raw deterministic score and the AI's narration — the frontend can display the trustworthy number and the readable explanation side by side.

If Gemini fails at any point (timeout, rate limit, malformed response), `AIProviderError` is caught, logged with its real cause server-side, and converted to a generic `503` — the rest of the app (weather, favorites, auth) is entirely unaffected, since no other feature depends on the AI call succeeding.

## 4. The Weather Intelligence Engine

`services/weather_intelligence.py` contains no network calls and no AI calls — it's pure, independently testable Python.

**Core scoring primitive:**
```python
def _linear_score(value, ideal_min, ideal_max, zero_at):
    # 100 within [ideal_min, ideal_max], falling off linearly to 0 at zero_at
```
Every factor (temperature, precipitation, wind, UV, AQI) is scored through this one shared shape, just with different bounds — auditable, tunable in one place, no duplicated logic.

**Activity-specific profiles** (`ACTIVITY_PROFILES`): each of the 10 activities has its own ideal temperature band *and* a realistic time-of-day window (`allowed_hours`). This second constraint was added after live testing surfaced a real bug — the scorer was recommending 3 AM as the "best time" for a picnic, because the math alone doesn't know picnics don't happen at 3 AM. The fix constrains the search space, not just the scoring, before a "best window" is ever chosen.

**Honesty by construction, not by prompt instruction alone**: the Travel Weather Brief feature marks each requested day `has_data: true/false` based on whether Open-Meteo's forecast actually covers it — days without real data are never scored, and the AI's system prompt is explicitly told to report the gap rather than fill it in. This was verified with a real test: requesting a trip 60+ days out returns a clean `422` with an honest message, before any AI call is even made.

## 5. AI Provider Layer

`services/ai/provider.py` is a ~50-line REST wrapper around Gemini's `generateContent` endpoint — deliberately not using Google's SDK, so the entire request/response shape is visible and swappable in one file.

Two real, non-obvious integration details discovered during development, both left as code comments for future maintainers:
- **Auth method**: Gemini's newer "Auth key" format (prefixed `AQ.`, replacing the older `AIzaSy...` format) must be sent via the `x-goog-api-key` header, not the legacy `?key=` query parameter.
- **Thinking tokens**: Gemini 3.x models spend part of the `maxOutputTokens` budget on internal reasoning before producing visible text. `generationConfig.thinkingConfig.thinkingLevel: "minimal"` disables this for Tempora's use case (short, factual explanations that don't need deep reasoning), which both fixed a real truncation bug and reduced latency/cost.

**Rate limiting** (`rate_limiter.py`) is intentionally in-memory, not Redis-backed: Tempora runs as a single Render instance, and Redis would be infrastructure overhead with no corresponding benefit at this scale. The known trade-off — counters reset on redeploy, and this wouldn't be correct across multiple instances — is accepted deliberately, not an oversight.

## 6. Database Layer

Three tables (`users`, `favorites`, `recent_searches`), SQLAlchemy 2.0 ORM, PostgreSQL via `psycopg` 3. Every query touching `favorites`/`recent_searches` filters by `current_user.id` — this is the single most security-critical pattern in the codebase, and it's verified in three independent ways across the project's development: manual two-account testing, and automated pytest isolation tests specifically asserting one user's data never appears in another's response.

**`pool_pre_ping=True`** is set on the SQLAlchemy engine specifically because Neon (serverless Postgres) suspends its compute after inactivity, silently closing pooled connections. Without this flag, the first request after any idle period would fail with a raw `OperationalError` — this was caught via a real production-like failure during local testing, not anticipated in advance, and is exactly the kind of connection-pool behavior that matters more on serverless infrastructure than a traditional always-on database.

## 7. Frontend Architecture

No build step, no framework — plain HTML/CSS/JS, loaded as separate `<script>` tags in a specific order (`config.js` -> `auth.js` -> `app.js` -> `tempo-ai.js`), since later files depend on globals defined in earlier ones.

**Theming**: the entire visual identity (the "Twilight" indigo/cyan palette) is driven by a small set of CSS custom properties (`--color-bg-start`, `--color-accent`, etc.) defined once in `:root`. Every component — including the AI panel, which was originally built with hardcoded hex colors during rapid feature development — was subsequently refactored to reference these variables, so a full theme change is now a ~10-line edit, not a find-and-replace across the whole stylesheet.

**The AI panel** (`tempo-ai.js`) is a single controller for all seven AI features, using `data-tab`/`data-tab-panel` attributes for generic tab-switching — adding an eighth feature later would need zero changes to the tab-switching logic itself, only a new panel and its own event handlers.

## 8. Testing Strategy

Automated tests (`backend/tests/`) mock the Gemini call (`generate_text`) rather than hitting the live API — this is a deliberate choice, not a shortcut: real API calls in a test suite would be slow, non-deterministic, and would consume the same limited free-tier daily quota the app itself needs. What the tests verify is Tempora's own logic — authentication, input validation, and cross-user isolation — which is exactly the part that's Tempora's responsibility to get right, independent of whether Gemini itself is behaving correctly on any given test run.

## 9. Deployment Topology

- **Vercel** serves the frontend as static files, root directory `frontend/`.
- **Render** runs the FastAPI app as a free-tier web service, root directory `backend/`, binding to Render's dynamically assigned `$PORT`.
- **Neon** hosts Postgres, connected via `DATABASE_URL`, encrypted in transit (`sslmode=require`).
- **CORS** is environment-driven (`CORS_ORIGINS`), not hardcoded — adding the production Vercel domain to Render's allowed origins was a one-line dashboard change, not a code deploy, because this was designed for exactly that moment early in development.

---

*This document reflects the system as actually implemented and deployed, not an aspirational design. Where a limitation is known and accepted rather than fixed, it's documented as such in the README's Known Limitations section.*
