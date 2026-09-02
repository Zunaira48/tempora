const explainWeatherButton = document.getElementById("explainWeatherButton");
const explainWeatherResult = document.getElementById("explainWeatherResult");

explainWeatherButton.addEventListener("click", async () => {
  if (!isLoggedIn()) {
    openAuthModal();
    return;
  }

  if (!currentCityName) {
    explainWeatherResult.hidden = false;
    explainWeatherResult.textContent = "Search for a city first.";
    return;
  }

  explainWeatherButton.disabled = true;
  explainWeatherResult.hidden = false;
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
        errorBody?.detail || "Tempora Copilot is temporarily unavailable. Weather data is still available.";
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
    explainWeatherResult.textContent = "Couldn't reach Tempora. Check your connection and try again.";
  } finally {
    explainWeatherButton.disabled = false;
  }
});