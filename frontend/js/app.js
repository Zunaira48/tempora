const API_BASE_URL = "http://127.0.0.1:8000";

const searchForm = document.getElementById("searchForm");
const cityInput = document.getElementById("cityInput");
const forecastGrid = document.getElementById("forecastGrid");
const recentSearchesContainer = document.getElementById("recentSearches");

const themeToggle = document.getElementById("themeToggle");
const themeIcon = themeToggle.querySelector(".theme-icon");

const sidebar = document.getElementById("sidebar");
const sidebarToggle = document.getElementById("sidebarToggle");

sidebarToggle.addEventListener("click", () => {
  sidebar.classList.toggle("is-open");
});

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

let currentUnit = localStorage.getItem("tempora-unit") || "c";
let lastWeatherData = null;
let lastHourlyData = null;

const unitToggle = document.getElementById("unitToggle");

function celsiusToFahrenheit(celsius) {
  return (celsius * 9) / 5 + 32;
}

function formatTemp(celsius) {
  const value = currentUnit === "f" ? celsiusToFahrenheit(celsius) : celsius;
  return `${Math.round(value)}°`;
}

unitToggle.addEventListener("click", (event) => {
  const button = event.target.closest(".unit-option");
  if (!button) return;

  currentUnit = button.dataset.unit;
  localStorage.setItem("tempora-unit", currentUnit);

  document.querySelectorAll(".unit-option").forEach((option) => {
    option.classList.toggle("is-active", option.dataset.unit === currentUnit);
  });

  if (lastWeatherData) {
    renderCurrentWeather(lastWeatherData);
  }
  if (lastHourlyData) {
    renderHourly(lastHourlyData.hours);
  }
});

async function fetchRecentSearches() {
  if (!isLoggedIn()) {
    recentSearchesContainer.innerHTML = "";
    return;
  }

  const response = await fetch(`${API_BASE_URL}/recent-searches`, {
    headers: authHeaders(),
  });

  if (response.status === 401) {
    handleAuthExpired();
    return;
  }

  if (!response.ok) {
    return;
  }

  const entries = await response.json();
  renderRecentSearches(entries);
}

function renderRecentSearches(entries) {
  recentSearchesContainer.innerHTML = "";

  entries.forEach((entry) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "recent-chip";
    chip.textContent = entry.city_name;
    chip.addEventListener("click", () => {
      cityInput.value = entry.city_name;
      searchForm.requestSubmit();
    });
    recentSearchesContainer.appendChild(chip);
  });
}

async function saveRecentSearch(city, country) {
  if (!isLoggedIn()) {
    return;
  }

  await fetch(`${API_BASE_URL}/recent-searches`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ city_name: city, country }),
  });

  fetchRecentSearches();
}

let currentFavorites = [];
let currentCityName = "";
let currentCountryName = "";
let currentLat = null;
let currentLon = null;

const favoriteSearchesContainer = document.getElementById("favoriteSearches");
const favoriteButton = document.getElementById("favoriteButton");
const favoriteIcon = favoriteButton.querySelector(".favorite-icon");

async function fetchFavorites() {
  if (!isLoggedIn()) {
    favoriteSearchesContainer.innerHTML = "";
    currentFavorites = [];
    updateFavoriteButton();
    return;
  }

  const response = await fetch(`${API_BASE_URL}/favorites`, {
    headers: authHeaders(),
  });

  if (response.status === 401) {
    handleAuthExpired();
    return;
  }

  if (!response.ok) {
    return;
  }

  currentFavorites = await response.json();
  renderFavoriteSearches();
  updateFavoriteButton();
}

function renderFavoriteSearches() {
  favoriteSearchesContainer.innerHTML = "";

  currentFavorites.forEach((favorite) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "favorite-chip";
    chip.textContent = `★ ${favorite.city_name}`;
    chip.addEventListener("click", () => {
      cityInput.value = favorite.city_name;
      searchForm.requestSubmit();
    });
    favoriteSearchesContainer.appendChild(chip);
  });
}

function findFavorite(city) {
  return currentFavorites.find((entry) => entry.city_name.toLowerCase() === city.toLowerCase());
}

function updateFavoriteButton() {
  const active = Boolean(currentCityName) && Boolean(findFavorite(currentCityName));
  favoriteButton.classList.toggle("is-active", active);
  favoriteIcon.textContent = active ? "★" : "☆";
}

favoriteButton.addEventListener("click", async () => {
  if (!currentCityName) {
    return;
  }

  if (!isLoggedIn()) {
    openAuthModal();
    return;
  }

  const existing = findFavorite(currentCityName);
  let response;

  if (existing) {
    response = await fetch(`${API_BASE_URL}/favorites/${existing.id}`, {
      method: "DELETE",
      headers: authHeaders(),
    });
  } else {
    response = await fetch(`${API_BASE_URL}/favorites`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({
        city_name: currentCityName,
        country: currentCountryName,
        latitude: currentLat,
        longitude: currentLon,
      }),
    });
  }

  if (response.status === 401) {
    handleAuthExpired();
    return;
  }

  await fetchFavorites();
});

fetchRecentSearches();
fetchFavorites();

window.addEventListener("tempora-auth-changed", () => {
  fetchRecentSearches();
  fetchFavorites();
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
    saveRecentSearch(currentWeather.city, currentWeather.country);
    fetchHourly(currentWeather.city);
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

async function fetchHourly(city) {
  const response = await fetch(`${API_BASE_URL}/weather/hourly?city=${encodeURIComponent(city)}`);
  if (!response.ok) {
    return;
  }
  const data = await response.json();
  lastHourlyData = data;
  renderHourly(data.hours);
}

function renderHourly(hours) {
  const hourlyStrip = document.getElementById("hourlyStrip");
  hourlyStrip.innerHTML = "";

  hours.slice(0, 24).forEach((hour) => {
    const card = document.createElement("div");
    card.className = "hourly-card";
    card.innerHTML = `
      <span class="hourly-time">${formatHourLabel(hour.time)}</span>
      <span class="hourly-temp">${formatTemp(hour.temperature_c)}</span>
      <span class="hourly-condition">${hour.condition_text}</span>
    `;
    hourlyStrip.appendChild(card);
  });
}

function formatHourLabel(isoString) {
  return new Date(isoString).toLocaleTimeString("en-US", { hour: "numeric" });
}

function setLoadingState() {
  const card = document.querySelector(".current-weather-card");
  card.classList.add("is-loading");
}

function renderCurrentWeather(data) {
  const card = document.querySelector(".current-weather-card");
  card.classList.remove("is-loading");

  lastWeatherData = data;

  document.querySelector(".city-name").textContent = `${data.city}, ${data.country}`;
  document.querySelector(".local-time").textContent = formatLocalTime(data.local_time);
  document.querySelector(".temperature-value").textContent = formatTemp(data.current.temperature_c);
  document.querySelector(".condition-text").textContent = data.current.condition_text;
  document.querySelector(".feels-like").textContent = `Feels like ${formatTemp(data.current.feels_like_c)}`;

  const stats = document.querySelectorAll(".stat-value");
  stats[0].textContent = `${data.current.humidity_percent}%`;
  stats[1].textContent = `${Math.round(data.current.wind_speed_kmh)} km/h`;
  stats[2].textContent = formatTime(data.sunrise);
  stats[3].textContent = formatTime(data.sunset);

  document.getElementById("uvValue").textContent =
    data.current.uv_index != null ? data.current.uv_index.toFixed(1) : "—";
  document.getElementById("aqiValue").textContent =
    data.current.air_quality_index != null ? data.current.air_quality_index : "—";

  currentCityName = data.city;
  currentCountryName = data.country;
  currentLat = data.latitude;
  currentLon = data.longitude;
  updateFavoriteButton();
}

function renderForecast(days) {
  forecastGrid.innerHTML = "";

  days.forEach((day) => {
    const card = document.createElement("div");
    card.className = "forecast-card";
    card.innerHTML = `
      <span class="forecast-day">${formatDayLabel(day.date)}</span>
      <span class="forecast-condition">${day.condition_text}</span>
      <span class="forecast-temps">${formatTemp(day.temperature_max_c)} / ${formatTemp(day.temperature_min_c)}</span>
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

document.querySelectorAll(".unit-option").forEach((option) => {
  option.classList.toggle("is-active", option.dataset.unit === currentUnit);
});