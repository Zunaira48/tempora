const activityToggle = document.getElementById("activityAdvisorToggle");
const activityPanel = document.getElementById("activityAdvisorPanel");
const activityClose = document.getElementById("activityAdvisorClose");
const activityResult = document.getElementById("activityAdvisorResult");
const activityButtons = document.querySelectorAll(".activity-btn");

function formatWindowTime(isoString) {
  const date = new Date(isoString);
  return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

activityToggle.addEventListener("click", () => {
  activityPanel.hidden = !activityPanel.hidden;
});

activityClose.addEventListener("click", () => {
  activityPanel.hidden = true;
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !activityPanel.hidden) {
    activityPanel.hidden = true;
  }
});

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
          errorBody?.detail || "Tempora Copilot is temporarily unavailable. Weather data is still available.";
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
      activityResult.textContent = "Couldn't reach Tempora. Check your connection and try again.";
    } finally {
      activityButtons.forEach((b) => (b.disabled = false));
    }
  });
});