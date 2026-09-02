const copilotToggle = document.getElementById("copilotToggle");
const copilotPanel = document.getElementById("copilotPanel");
const copilotClose = document.getElementById("copilotClose");
const copilotMessages = document.getElementById("copilotMessages");
const copilotForm = document.getElementById("copilotForm");
const copilotInput = document.getElementById("copilotInput");
const copilotSend = document.getElementById("copilotSend");

function openCopilot() {
  copilotPanel.hidden = false;
  copilotInput.focus();
}

function closeCopilot() {
  copilotPanel.hidden = true;
}

function appendCopilotMessage(text, role) {
  const bubble = document.createElement("div");
  bubble.className = `copilot-message ${role}`;
  bubble.textContent = text;
  copilotMessages.appendChild(bubble);
  copilotMessages.scrollTop = copilotMessages.scrollHeight;
}

copilotToggle.addEventListener("click", () => {
  if (copilotPanel.hidden) {
    openCopilot();
  } else {
    closeCopilot();
  }
});

copilotToggle.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    copilotToggle.click();
  }
});

copilotClose.addEventListener("click", closeCopilot);

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !copilotPanel.hidden) {
    closeCopilot();
  }
});

copilotForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const message = copilotInput.value.trim();
  if (!message) {
    return;
  }

  if (!isLoggedIn()) {
    appendCopilotMessage("Please log in to use Tempora Copilot.", "error");
    openAuthModal();
    return;
  }

  if (!currentCityName) {
    appendCopilotMessage("Search for a city first, then ask Copilot about it.", "error");
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

    if (response.status === 429) {
      const errorBody = await response.json().catch(() => null);
      appendCopilotMessage(errorBody?.detail || "You're asking too quickly. Please wait a moment.", "error");
      return;
    }

    if (!response.ok) {
      const errorBody = await response.json().catch(() => null);
      appendCopilotMessage(
        errorBody?.detail || "Tempora Copilot is temporarily unavailable. Weather data is still available.",
        "error"
      );
      return;
    }

    const data = await response.json();
    appendCopilotMessage(data.reply, "assistant");
  } catch (error) {
    appendCopilotMessage("Couldn't reach Tempora Copilot. Check your connection and try again.", "error");
  } finally {
    copilotInput.disabled = false;
    copilotSend.disabled = false;
    copilotInput.focus();
  }
});