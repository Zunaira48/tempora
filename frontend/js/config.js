// Determines which backend API this frontend talks to.
// Local development (Live Server on 127.0.0.1/localhost) automatically
// points at the local FastAPI server. Production deployments should set
// window.TEMPORA_API_BASE_URL before this file loads (see index.html),
// or edit the fallback below after deploying to Render.

const isLocalDev = ["127.0.0.1", "localhost"].includes(window.location.hostname);

const API_BASE_URL = isLocalDev
  ? "http://127.0.0.1:8000"
  : (window.TEMPORA_API_BASE_URL || "https://tempora-api.onrender.com");