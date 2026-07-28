const API_BASE_URL = "http://127.0.0.1:8000";

const searchForm = document.getElementById("searchForm");
const cityInput = document.getElementById("cityInput");
const forecastGrid = document.getElementById("forecastGrid");
const recentSearchesContainer = document.getElementById("recentSearches");

const themeToggle = document.getElementById("themeToggle");
const themeIcon = themeToggle.querySelector(".theme-icon");

const RECENT_SEARCHES_KEY = "tempora-recent-searches";

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

function getRecentSearches() {
  const stored = localStorage.getItem(RECENT_SEARCHES_KEY);
  return stored ? JSON.parse(stored) : [];
}

function saveRecentSearch(city) {
  let recent = getRecentSearches();
  recent = recent.filter((entry) => entry.toLowerCase() !== city.toLowerCase());
  recent.unshift(city);
  recent = recent.slice(0, 5);
  localStorage.setItem(RECENT_SEARCHES_KEY, JSON.stringify(recent));
  renderRecentSearches();
}

function renderRecentSearches() {
  const recent = getRecentSearches();
  recentSearchesContainer.innerHTML = "";

  recent.forEach((city) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "recent-chip";
    chip.textContent = city;
    chip.addEventListener("click", () => {
      cityInput.value = city;
      searchForm.requestSubmit();
    });
    recentSearchesContainer.appendChild(chip);
  });
}

renderRecentSearches();

const FAVORITES_KEY = "tempora-favorite-cities";
const favoriteSearchesContainer = document.getElementById("favoriteSearches");
const favoriteButton = document.getElementById("favoriteButton");
const favoriteIcon = favoriteButton.querySelector(".favorite-icon");

let currentCityName = "";

function getFavorites() {
  const stored = localStorage.getItem(FAVORITES_KEY);
  return stored ? JSON.parse(stored) : [];
}

function isFavorite(city) {
  return getFavorites().some((entry) => entry.toLowerCase() === city.toLowerCase());
}

function toggleFavorite(city) {
  let favorites = getFavorites();

  if (isFavorite(city)) {
    favorites = favorites.filter((entry) => entry.toLowerCase() !== city.toLowerCase());
  } else {
    favorites.push(city);
  }

  localStorage.setItem(FAVORITES_KEY, JSON.stringify(favorites));
  updateFavoriteButton(city);
  renderFavoriteSearches();
}

function updateFavoriteButton(city) {
  const active = isFavorite(city);
  favoriteButton.classList.toggle("is-active", active);
  favoriteIcon.textContent = active ? "★" : "☆";
}

function renderFavoriteSearches() {
  const favorites = getFavorites();
  favoriteSearchesContainer.innerHTML = "";

  favorites.forEach((city) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "favorite-chip";
    chip.textContent = `★ ${city}`;
    chip.addEventListener("click", () => {
      cityInput.value = city;
      searchForm.requestSubmit();
    });
    favoriteSearchesContainer.appendChild(chip);
  });
}

favoriteButton.addEventListener("click", () => {
  if (currentCityName) {
    toggleFavorite(currentCityName);
  }
});

renderFavoriteSearches();

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
    saveRecentSearch(currentWeather.city);
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

  currentCityName = data.city;
  updateFavoriteButton(data.city);
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