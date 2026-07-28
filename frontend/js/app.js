const API_BASE_URL = "http://127.0.0.1:8000";

const searchForm = document.getElementById("searchForm");
const cityInput = document.getElementById("cityInput");
const forecastGrid = document.getElementById("forecastGrid");

const themeToggle = document.getElementById("themeToggle");
const themeIcon = themeToggle.querySelector(".theme-icon");

function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  themeIcon.textContent = theme === "light" ? "☀️" : "🌙";
  localStorage.setItem("tempora-theme", theme);
}

const savedTheme = localStorage.getItem("tempora-theme") || "dark";
applyTheme(savedTheme);

themeToggle.addEventListener("click", () => {
  const currentTheme = document.documentElement.getAttribute("data-theme");
  const nextTheme = currentTheme === "light" ? "dark" : "light";
  applyTheme(nextTheme);
});

searchForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const city = cityInput.value.trim();
  if (!city) {
    return;
  }

  setLoadingState();

  try {
    const [currentWeather, forecast] = await Promise.all([
      fetchCurrentWeather(city),
      fetchForecast(city),
    ]);

    renderCurrentWeather(currentWeather);
    renderForecast(forecast.days);
  } catch (error) {
    renderError(error.message);
  }
});

async function fetchCurrentWeather(city) {
  const response = await fetch(`${API_BASE_URL}/weather?city=${encodeURIComponent(city)}`);

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error(`Couldn't find "${city}". Check the spelling and try again.`);
    }
    throw new Error("Something went wrong fetching the weather. Please try again.");
  }

  return response.json();
}

async function fetchForecast(city) {
  const response = await fetch(`${API_BASE_URL}/weather/forecast?city=${encodeURIComponent(city)}`);

  if (!response.ok) {
    throw new Error("Couldn't load the forecast. Please try again.");
  }

  return response.json();
}

function setLoadingState() {
  const card = document.querySelector(".current-weather-card");
  card.classList.add("is-loading");
}

function renderCurrentWeather(data) {
  const card = document.querySelector(".current-weather-card");
  card.classList.remove("is-loading");

  document.querySelector(".city-name").textContent = `${data.city}, ${data.country}`;
  document.querySelector(".local-time").textContent = formatLocalTime(data.local_time);
  document.querySelector(".temperature-value").textContent = `${Math.round(data.current.temperature_c)}°`;
  document.querySelector(".condition-text").textContent = data.current.condition_text;
  document.querySelector(".feels-like").textContent = `Feels like ${Math.round(data.current.feels_like_c)}°`;

  const stats = document.querySelectorAll(".stat-value");
  stats[0].textContent = `${data.current.humidity_percent}%`;
  stats[1].textContent = `${Math.round(data.current.wind_speed_kmh)} km/h`;
  stats[2].textContent = formatTime(data.sunrise);
  stats[3].textContent = formatTime(data.sunset);
}

function renderForecast(days) {
  forecastGrid.innerHTML = "";

  days.forEach((day) => {
    const card = document.createElement("div");
    card.className = "forecast-card";
    card.innerHTML = `
      <span class="forecast-day">${formatDayLabel(day.date)}</span>
      <span class="forecast-condition">${day.condition_text}</span>
      <span class="forecast-temps">${Math.round(day.temperature_max_c)}° / ${Math.round(day.temperature_min_c)}°</span>
    `;
    forecastGrid.appendChild(card);
  });
}

function renderError(message) {
  const card = document.querySelector(".current-weather-card");
  card.classList.remove("is-loading");
  document.querySelector(".city-name").textContent = "Oops";
  document.querySelector(".local-time").textContent = message;
}

function formatLocalTime(isoString) {
  const date = new Date(isoString);
  return date.toLocaleDateString("en-US", { weekday: "long" }) + ", " +
    date.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
}

function formatTime(isoString) {
  return new Date(isoString).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
}

function formatDayLabel(dateString) {
  return new Date(dateString).toLocaleDateString("en-US", { weekday: "short" });
}