const tempoAiButton = document.getElementById("tempoAiButton");
const tempoAiPanel = document.getElementById("tempoAiPanel");
const tempoAiClose = document.getElementById("tempoAiClose");
const tempoAiTabs = document.querySelectorAll(".tempo-ai-tab");
const tempoAiTabPanels = document.querySelectorAll(".tempo-ai-tab-panel");

tempoAiButton.addEventListener("click", () => {
  tempoAiPanel.hidden = !tempoAiPanel.hidden;
});

tempoAiClose.addEventListener("click", () => {
  tempoAiPanel.hidden = true;
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !tempoAiPanel.hidden) {
    tempoAiPanel.hidden = true;
  }
});

tempoAiTabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    tempoAiTabs.forEach((t) => t.classList.remove("is-active"));
    tab.classList.add("is-active");

    tempoAiTabPanels.forEach((panel) => {
      panel.classList.toggle("is-hidden", panel.dataset.tabPanel !== tab.dataset.tab);
    });
  });
});

/* ---------- Chat (Copilot) ---------- */

const copilotMessages = document.getElementById("copilotMessages");
const copilotForm = document.getElementById("copilotForm");
const copilotInput = document.getElementById("copilotInput");
const copilotSend = document.getElementById("copilotSend");

function appendCopilotMessage(text, role) {
  const bubble = document.createElement("div");
  bubble.className = `copilot-message ${role}`;
  bubble.textContent = text;
  copilotMessages.appendChild(bubble);
  copilotMessages.scrollTop = copilotMessages.scrollHeight;
}

copilotForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const message = copilotInput.value.trim();
  if (!message) {
    return;
  }

  if (!isLoggedIn()) {
    appendCopilotMessage("Please log in to use Tempora AI.", "error");
    openAuthModal();
    return;
  }

  if (!currentCityName) {
    appendCopilotMessage("Search for a city first, then ask about it.", "error");
    return;
  }

  appendCopilotMessage(message, "user");
  copilotInput.value = "";
  copilotInput.disabled = true;
  copilotSend.disabled = true;

  try {
    const response = await fetch(`${API_BASE_URL}/ai/copilot`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ city: currentCityName, message }),
    });

    if (response.status === 401) {
      handleAuthExpired();
      appendCopilotMessage("Your session expired. Please log in again.", "error");
      return;
    }

    if (!response.ok) {
      const errorBody = await response.json().catch(() => null);
      appendCopilotMessage(
        errorBody?.detail || errorBody?.error || "Tempora AI is temporarily unavailable. Weather data is still available.",
        "error"
      );
      return;
    }

    const data = await response.json();
    appendCopilotMessage(data.reply, "assistant");
  } catch (error) {
    appendCopilotMessage("Couldn't reach Tempora AI. Check your connection and try again.", "error");
  } finally {
    copilotInput.disabled = false;
    copilotSend.disabled = false;
    copilotInput.focus();
  }
});

/* ---------- Explain My Weather ---------- */

const explainWeatherButton = document.getElementById("explainWeatherButton");
const explainWeatherResult = document.getElementById("explainWeatherResult");

explainWeatherButton.addEventListener("click", async () => {
  if (!isLoggedIn()) {
    openAuthModal();
    return;
  }

  if (!currentCityName) {
    explainWeatherResult.textContent = "Search for a city first.";
    return;
  }

  explainWeatherButton.disabled = true;
  explainWeatherResult.textContent = "Thinking...";

  try {
    const response = await fetch(`${API_BASE_URL}/ai/explain-weather`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ city: currentCityName }),
    });

    if (response.status === 401) {
      handleAuthExpired();
      explainWeatherResult.textContent = "Your session expired. Please log in again.";
      return;
    }

    if (!response.ok) {
      const errorBody = await response.json().catch(() => null);
      explainWeatherResult.textContent =
        errorBody?.detail || errorBody?.error || "Tempora AI is temporarily unavailable. Weather data is still available.";
      return;
    }

    const data = await response.json();
    explainWeatherResult.innerHTML = "";

    const scoreLine = document.createElement("div");
    scoreLine.className = "explain-weather-score";
    scoreLine.textContent = `Outdoor Suitability: ${data.score}/100`;
    explainWeatherResult.appendChild(scoreLine);

    const summaryLine = document.createElement("div");
    summaryLine.textContent = data.summary;
    explainWeatherResult.appendChild(summaryLine);
  } catch (error) {
    explainWeatherResult.textContent = "Couldn't reach Tempora AI. Check your connection and try again.";
  } finally {
    explainWeatherButton.disabled = false;
  }
});

/* ---------- Activity Advisor ---------- */

const activityResult = document.getElementById("activityAdvisorResult");
const activityButtons = document.querySelectorAll(".activity-btn");

function formatWindowTime(isoString) {
  const date = new Date(isoString);
  return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

activityButtons.forEach((button) => {
  button.addEventListener("click", async () => {
    if (!isLoggedIn()) {
      openAuthModal();
      return;
    }

    if (!currentCityName) {
      activityResult.textContent = "Search for a city first.";
      return;
    }

    activityButtons.forEach((b) => b.classList.remove("active"));
    button.classList.add("active");
    activityButtons.forEach((b) => (b.disabled = true));
    activityResult.textContent = "Checking the forecast...";

    try {
      const response = await fetch(`${API_BASE_URL}/ai/activity-advisor`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ city: currentCityName, activity: button.dataset.activity }),
      });

      if (response.status === 401) {
        handleAuthExpired();
        activityResult.textContent = "Your session expired. Please log in again.";
        return;
      }

      if (!response.ok) {
        const errorBody = await response.json().catch(() => null);
        activityResult.textContent =
          errorBody?.detail || errorBody?.error || "Tempora AI is temporarily unavailable. Weather data is still available.";
        return;
      }

      const data = await response.json();
      activityResult.innerHTML = "";

      const scoreEl = document.createElement("div");
      scoreEl.className = "activity-score";
      scoreEl.textContent = `${data.activity_label}: ${data.score}/100`;
      activityResult.appendChild(scoreEl);

      const windowEl = document.createElement("div");
      windowEl.className = "activity-window";
      windowEl.textContent = `Best window: ${formatWindowTime(data.best_window_start)} - ${formatWindowTime(data.best_window_end)}`;
      activityResult.appendChild(windowEl);

      const list = document.createElement("ul");
      data.reasons.forEach((reason) => {
        const li = document.createElement("li");
        li.textContent = reason;
        list.appendChild(li);
      });
      activityResult.appendChild(list);

      const summaryEl = document.createElement("div");
      summaryEl.textContent = data.summary;
      activityResult.appendChild(summaryEl);
    } catch (error) {
      activityResult.textContent = "Couldn't reach Tempora AI. Check your connection and try again.";
    } finally {
      activityButtons.forEach((b) => (b.disabled = false));
    }
  });
});


/* ---------- Plan My Day ---------- */

const planMyDayForm = document.getElementById("planMyDayForm");
const planMyDayInput = document.getElementById("planMyDayInput");
const planMyDaySubmit = document.getElementById("planMyDaySubmit");
const planMyDayResult = document.getElementById("planMyDayResult");

function formatPlanTime(isoString) {
  const date = new Date(isoString);
  return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

planMyDayForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const planText = planMyDayInput.value.trim();
  if (!planText) {
    return;
  }

  if (!isLoggedIn()) {
    openAuthModal();
    return;
  }

  if (!currentCityName) {
    planMyDayResult.textContent = "Search for a city first.";
    return;
  }

  planMyDaySubmit.disabled = true;
  planMyDayResult.textContent = "Planning your day...";

  try {
    const response = await fetch(`${API_BASE_URL}/ai/plan-my-day`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ city: currentCityName, plan_text: planText }),
    });

    if (response.status === 401) {
      handleAuthExpired();
      planMyDayResult.textContent = "Your session expired. Please log in again.";
      return;
    }

    if (!response.ok) {
      const errorBody = await response.json().catch(() => null);
      planMyDayResult.textContent =
        errorBody?.detail || errorBody?.error || "Tempora AI is temporarily unavailable. Weather data is still available.";
      return;
    }

    const data = await response.json();
    planMyDayResult.innerHTML = "";

    data.schedule.forEach((item) => {
      const row = document.createElement("div");
      row.className = "plan-event";

      const time = document.createElement("div");
      time.className = "plan-event-time";
      time.textContent = formatPlanTime(item.time);
      row.appendChild(time);

      const details = document.createElement("div");
      details.className = "plan-event-details";

      const label = document.createElement("div");
      label.className = "plan-event-label";
      label.textContent = item.label;
      details.appendChild(label);

      const meta = document.createElement("div");
      meta.className = "plan-event-meta";
      meta.textContent = `${Math.round(item.temperature_c)}°C · ${item.comfort_label}`;
      details.appendChild(meta);

      row.appendChild(details);
      planMyDayResult.appendChild(row);
    });

    const summaryEl = document.createElement("div");
    summaryEl.className = "plan-summary";
    summaryEl.textContent = data.summary;
    planMyDayResult.appendChild(summaryEl);
  } catch (error) {
    planMyDayResult.textContent = "Couldn't reach Tempora AI. Check your connection and try again.";
  } finally {
    planMyDaySubmit.disabled = false;
  }
});


/* ---------- City Comparison ---------- */

const compareCitiesForm = document.getElementById("compareCitiesForm");
const compareCityA = document.getElementById("compareCityA");
const compareCityB = document.getElementById("compareCityB");
const comparePurpose = document.getElementById("comparePurpose");
const compareCitiesSubmit = document.getElementById("compareCitiesSubmit");
const compareCitiesResult = document.getElementById("compareCitiesResult");

function renderCityCard(summary) {
  const card = document.createElement("div");
  card.className = "compare-city-card";

  const name = document.createElement("div");
  name.className = "compare-city-name";
  name.textContent = `${summary.city}, ${summary.country}`;
  card.appendChild(name);

  const rows = [
    `${Math.round(summary.temperature_c)}°C (feels ${Math.round(summary.feels_like_c)}°C)`,
    `Humidity ${summary.humidity_percent}%`,
    `Wind ${Math.round(summary.wind_speed_kmh)} km/h`,
    summary.aqi != null ? `AQI ${summary.aqi}` : "AQI unavailable",
    summary.uv_index != null ? `UV ${summary.uv_index.toFixed(1)}` : "UV unavailable",
  ];

  rows.forEach((text) => {
    const row = document.createElement("div");
    row.className = "compare-city-stat";
    row.textContent = text;
    card.appendChild(row);
  });

  return card;
}

compareCitiesForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const cityA = compareCityA.value.trim();
  const cityB = compareCityB.value.trim();

  if (!cityA || !cityB) {
    compareCitiesResult.textContent = "Enter both cities to compare.";
    return;
  }

  if (!isLoggedIn()) {
    openAuthModal();
    return;
  }

  compareCitiesSubmit.disabled = true;
  compareCitiesResult.textContent = "Comparing...";

  try {
    const response = await fetch(`${API_BASE_URL}/ai/compare-cities`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ city_a: cityA, city_b: cityB, purpose: comparePurpose.value.trim() }),
    });

    if (response.status === 401) {
      handleAuthExpired();
      compareCitiesResult.textContent = "Your session expired. Please log in again.";
      return;
    }

    if (!response.ok) {
      const errorBody = await response.json().catch(() => null);
      compareCitiesResult.textContent =
        errorBody?.detail || errorBody?.error || "Tempora AI is temporarily unavailable. Weather data is still available.";
      return;
    }

    const data = await response.json();
    compareCitiesResult.innerHTML = "";

    const grid = document.createElement("div");
    grid.className = "compare-grid";
    grid.appendChild(renderCityCard(data.city_a));
    grid.appendChild(renderCityCard(data.city_b));
    compareCitiesResult.appendChild(grid);

    const summaryEl = document.createElement("div");
    summaryEl.className = "compare-summary";
    summaryEl.textContent = data.summary;
    compareCitiesResult.appendChild(summaryEl);
  } catch (error) {
    compareCitiesResult.textContent = "Couldn't reach Tempora AI. Check your connection and try again.";
  } finally {
    compareCitiesSubmit.disabled = false;
  }
});


/* ---------- Travel Weather Brief ---------- */

const travelBriefForm = document.getElementById("travelBriefForm");
const travelStartDate = document.getElementById("travelStartDate");
const travelEndDate = document.getElementById("travelEndDate");
const travelPurpose = document.getElementById("travelPurpose");
const travelBriefSubmit = document.getElementById("travelBriefSubmit");
const travelBriefResult = document.getElementById("travelBriefResult");

function formatTravelDate(dateString) {
  return new Date(dateString + "T00:00:00").toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" });
}

travelBriefForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  if (!travelStartDate.value || !travelEndDate.value) {
    travelBriefResult.textContent = "Choose both a start and end date.";
    return;
  }

  if (!isLoggedIn()) {
    openAuthModal();
    return;
  }

  if (!currentCityName) {
    travelBriefResult.textContent = "Search for a city first.";
    return;
  }

  travelBriefSubmit.disabled = true;
  travelBriefResult.textContent = "Building your travel brief...";

  try {
    const response = await fetch(`${API_BASE_URL}/ai/travel-brief`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({
        city: currentCityName,
        start_date: travelStartDate.value,
        end_date: travelEndDate.value,
        purpose: travelPurpose.value.trim(),
      }),
    });

    if (response.status === 401) {
      handleAuthExpired();
      travelBriefResult.textContent = "Your session expired. Please log in again.";
      return;
    }

    if (!response.ok) {
      const errorBody = await response.json().catch(() => null);
      travelBriefResult.textContent =
        errorBody?.detail || errorBody?.error || "Tempora AI is temporarily unavailable. Weather data is still available.";
      return;
    }

    const data = await response.json();
    travelBriefResult.innerHTML = "";

    const strip = document.createElement("div");
    strip.className = "travel-day-strip";

    data.days.forEach((day) => {
      const card = document.createElement("div");
      card.className = "travel-day-card";
      if (!day.has_data) card.classList.add("no-data");
      if (day.date === data.best_day) card.classList.add("is-best");

      const dateEl = document.createElement("div");
      dateEl.className = "travel-day-date";
      dateEl.textContent = formatTravelDate(day.date);
      card.appendChild(dateEl);

      if (day.has_data) {
        const temps = document.createElement("div");
        temps.className = "travel-day-temps";
        temps.textContent = `${Math.round(day.temperature_max_c)}° / ${Math.round(day.temperature_min_c)}°`;
        card.appendChild(temps);

        const score = document.createElement("div");
        score.className = "travel-day-score";
        score.textContent = `${day.score}/100`;
        card.appendChild(score);
      } else {
        const noData = document.createElement("div");
        noData.className = "travel-day-nodata";
        noData.textContent = "No forecast yet";
        card.appendChild(noData);
      }

      strip.appendChild(card);
    });

    travelBriefResult.appendChild(strip);

    const summaryEl = document.createElement("div");
    summaryEl.className = "travel-summary";
    summaryEl.textContent = data.summary;
    travelBriefResult.appendChild(summaryEl);
  } catch (error) {
    travelBriefResult.textContent = "Couldn't reach Tempora AI. Check your connection and try again.";
  } finally {
    travelBriefSubmit.disabled = false;
  }
});