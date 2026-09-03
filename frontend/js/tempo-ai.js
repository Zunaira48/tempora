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
        errorBody?.detail || "Tempora AI is temporarily unavailable. Weather data is still available.",
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
        errorBody?.detail || "Tempora AI is temporarily unavailable. Weather data is still available.";
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
          errorBody?.detail || "Tempora AI is temporarily unavailable. Weather data is still available.";
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