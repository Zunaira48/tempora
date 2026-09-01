const AUTH_API_BASE = API_BASE_URL;
const TOKEN_KEY = "tempora-auth-token";

const authModalOverlay = document.getElementById("authModalOverlay");
const authModalClose = document.getElementById("authModalClose");
const accountButton = document.getElementById("accountButton");

const loginTab = document.getElementById("loginTab");
const registerTab = document.getElementById("registerTab");
const loginForm = document.getElementById("loginForm");
const registerForm = document.getElementById("registerForm");
const loginError = document.getElementById("loginError");
const registerError = document.getElementById("registerError");

function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
  updateAccountButton();
}

function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
  updateAccountButton();
}

function isLoggedIn() {
  return Boolean(getToken());
}

function authHeaders() {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}
function handleAuthExpired() {
  clearToken();
  openAuthModal();
}

function updateAccountButton() {
  accountButton.classList.toggle("is-logged-in", isLoggedIn());
  accountButton.querySelector(".account-icon").textContent = isLoggedIn() ? "🟢" : "👤";
}

let lastFocusedElement = null;

function getFocusableModalElements() {
  return authModalOverlay.querySelectorAll(
    'button, input, [href], select, textarea, [tabindex]:not([tabindex="-1"])'
  );
}

function openAuthModal() {
  lastFocusedElement = document.activeElement;
  authModalOverlay.classList.add("is-open");

  const focusable = getFocusableModalElements();
  if (focusable.length > 0) {
    focusable[0].focus();
  }
}

function closeAuthModal() {
  authModalOverlay.classList.remove("is-open");
  loginError.textContent = "";
  registerError.textContent = "";

  if (lastFocusedElement) {
    lastFocusedElement.focus();
    lastFocusedElement = null;
  }
}

document.addEventListener("keydown", (event) => {
  if (!authModalOverlay.classList.contains("is-open")) {
    return;
  }

  if (event.key === "Escape") {
    closeAuthModal();
    return;
  }

  if (event.key === "Tab") {
    const focusable = Array.from(getFocusableModalElements());
    if (focusable.length === 0) {
      return;
    }

    const first = focusable[0];
    const last = focusable[focusable.length - 1];

    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }
});

function switchToLoginTab() {
  loginTab.classList.add("is-active");
  registerTab.classList.remove("is-active");
  loginForm.classList.remove("is-hidden");
  registerForm.classList.add("is-hidden");
}

function switchToRegisterTab() {
  registerTab.classList.add("is-active");
  loginTab.classList.remove("is-active");
  registerForm.classList.remove("is-hidden");
  loginForm.classList.add("is-hidden");
}

accountButton.addEventListener("click", () => {
  if (isLoggedIn()) {
    const confirmed = confirm("Log out of Tempora?");
    if (confirmed) {
      clearToken();
      window.dispatchEvent(new Event("tempora-auth-changed"));
    }
    return;
  }
  openAuthModal();
});

authModalClose.addEventListener("click", closeAuthModal);

authModalOverlay.addEventListener("click", (event) => {
  if (event.target === authModalOverlay) {
    closeAuthModal();
  }
});

loginTab.addEventListener("click", switchToLoginTab);
registerTab.addEventListener("click", switchToRegisterTab);

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  loginError.textContent = "";

  const email = document.getElementById("loginEmail").value.trim();
  const password = document.getElementById("loginPassword").value;

  try {
    const response = await fetch(`${AUTH_API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });

    if (!response.ok) {
      throw new Error("Incorrect email or password");
    }

    const data = await response.json();
    setToken(data.access_token);
    loginForm.reset();
    closeAuthModal();
    window.dispatchEvent(new Event("tempora-auth-changed"));
  } catch (error) {
    loginError.textContent = error.message;
  }
});

registerForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  registerError.textContent = "";

  const email = document.getElementById("registerEmail").value.trim();
  const password = document.getElementById("registerPassword").value;

  try {
    const response = await fetch(`${AUTH_API_BASE}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });

    if (!response.ok) {
      const errorBody = await response.json().catch(() => null);
      throw new Error(errorBody?.detail || "Could not create account");
    }

    const data = await response.json();
    setToken(data.access_token);
    registerForm.reset();
    closeAuthModal();
    window.dispatchEvent(new Event("tempora-auth-changed"));
  } catch (error) {
    registerError.textContent = error.message;
  }
});

updateAccountButton();