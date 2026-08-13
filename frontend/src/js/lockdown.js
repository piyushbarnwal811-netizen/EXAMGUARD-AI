const LOCKDOWN_API_BASE = window.EXAMGUARD_API_BASE || "http://127.0.0.1:8000/api";
let lockdownStarted = false;
let examSubmitted = false;
let lastSecurityEventAt = new Map();
let resumeTimer = null;

function lockdownAuthHeaders() {
  const token = localStorage.getItem("examguard_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function lockdownContext(extraDetails = {}) {
  return {
    page_url: window.location.href,
    visibility_state: document.visibilityState,
    fullscreen_active: Boolean(document.fullscreenElement),
    lockdown_started: lockdownStarted,
    ...extraDetails,
  };
}

function setLockdownStatus(message, type = "") {
  const status = document.querySelector("[data-lockdown-status]");
  const indicator = document.querySelector("[data-lockdown-indicator]");
  if (status) status.textContent = message;
  if (indicator) indicator.className = `status-pill ${type}`.trim();
}

function setLockdownButtonText(message) {
  const button = document.querySelector("[data-lockdown-start]");
  if (button) button.textContent = message;
}

function lockdownEnforced() {
  return lockdownStarted && !examSubmitted;
}

function shouldSkipDuplicate(eventType, details) {
  const key = `${eventType}:${details.trigger || ""}:${details.key || ""}`;
  const now = Date.now();
  const previous = lastSecurityEventAt.get(key) || 0;
  lastSecurityEventAt.set(key, now);
  return now - previous < 1200;
}

function notifySecurityEvent(eventType, message = "", details = {}, options = {}) {
  const eventDetails = lockdownContext(details);
  if (shouldSkipDuplicate(eventType, eventDetails)) return;

  if (window.ExamGuardTracking?.sendEvent) {
    window.ExamGuardTracking.sendEvent(
      eventType,
      message,
      eventDetails,
      options
    ).catch(() => undefined);
    return;
  }

  fetch(`${LOCKDOWN_API_BASE}/tracking/events`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...lockdownAuthHeaders(),
    },
    body: JSON.stringify({
      event_type: eventType,
      message,
      client_timestamp: new Date().toISOString(),
      details: eventDetails,
    }),
    keepalive: Boolean(options.keepalive),
  }).catch(() => undefined);
}

async function enterFullscreen() {
  const root = document.documentElement;
  if (root.requestFullscreen) {
    await root.requestFullscreen();
  }
}

function ensureFullscreenGuard() {
  let guard = document.querySelector("[data-fullscreen-guard]");
  if (guard) return guard;

  guard = document.createElement("div");
  guard.className = "fullscreen-guard";
  guard.hidden = true;
  guard.dataset.fullscreenGuard = "true";
  guard.innerHTML = `
    <section class="fullscreen-guard-panel">
      <p class="eyebrow">Fullscreen Required</p>
      <h2>Resume Fullscreen</h2>
      <p class="muted">The exam is paused until fullscreen is restored.</p>
      <div class="actions">
        <button type="button" data-fullscreen-resume>Resume Fullscreen</button>
      </div>
    </section>
  `;
  guard.querySelector("[data-fullscreen-resume]")?.addEventListener("click", () => {
    requestFullscreenResume("guard_button");
  });
  document.body.appendChild(guard);
  return guard;
}

function showFullscreenGuard() {
  if (!lockdownEnforced() || document.fullscreenElement) return;
  ensureFullscreenGuard().hidden = false;
}

function hideFullscreenGuard() {
  const guard = document.querySelector("[data-fullscreen-guard]");
  if (guard) guard.hidden = true;
}

async function requestFullscreenResume(trigger = "auto_resume") {
  if (!lockdownEnforced() || document.fullscreenElement || document.hidden) return false;

  try {
    await enterFullscreen();
    setLockdownStatus("Fullscreen active", "success");
    hideFullscreenGuard();
    notifySecurityEvent("FULLSCREEN_ENTER", "Student re-entered fullscreen mode.", {
      trigger,
    });
    return true;
  } catch (error) {
    setLockdownStatus("Resume fullscreen required", "warning");
    setLockdownButtonText("Resume Fullscreen");
    showFullscreenGuard();
    notifySecurityEvent("FULLSCREEN_RESUME_FAILED", "Fullscreen resume needs student action.", {
      trigger,
      error_name: error?.name || "UnknownError",
    });
    return false;
  }
}

function scheduleFullscreenResume(trigger = "scheduled_resume") {
  window.clearTimeout(resumeTimer);
  resumeTimer = window.setTimeout(() => {
    requestFullscreenResume(trigger);
  }, 250);
}

function blockRestrictedKeys(event) {
  const key = event.key.toUpperCase();
  const blockedCombos =
    event.key === "F12" ||
    (event.ctrlKey && event.shiftKey && ["I", "J", "C"].includes(key)) ||
    ((event.ctrlKey || event.metaKey) && ["U", "S", "P"].includes(key)) ||
    (event.altKey && key === "TAB") ||
    (lockdownEnforced() && event.key === "Escape");

  if (blockedCombos) {
    event.preventDefault();
    if (event.key === "Escape") scheduleFullscreenResume("escape_key");
    notifySecurityEvent("BLOCKED_KEY", `Blocked key: ${event.key}`, {
      trigger: "keydown",
      key: event.key,
      code: event.code,
      ctrl_key: event.ctrlKey,
      shift_key: event.shiftKey,
      alt_key: event.altKey,
      meta_key: event.metaKey,
    });
  }
}

async function startLockdown(options = {}) {
  if (examSubmitted) return false;
  lockdownStarted = true;
  try {
    await enterFullscreen();
    setLockdownStatus("Fullscreen active", "success");
    setLockdownButtonText("Resume Fullscreen");
    hideFullscreenGuard();
    notifySecurityEvent("LOCKDOWN_START", "Fullscreen lockdown started.", {
      trigger: options.requestedBy || "manual_start",
    });
    notifySecurityEvent("FULLSCREEN_ENTER", "Student entered fullscreen mode.", {
      trigger: options.requestedBy || "manual_start",
    });
    return true;
  } catch (error) {
    setLockdownStatus("Fullscreen permission denied", "warning");
    setLockdownButtonText("Resume Fullscreen");
    showFullscreenGuard();
    notifySecurityEvent("FULLSCREEN_DENIED", "Fullscreen permission was denied.", {
      trigger: options.requestedBy || "manual_start",
      error_name: error?.name || "UnknownError",
    });
    return false;
  }
}

document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    setLockdownStatus("Exam tab hidden", "warning");
    notifySecurityEvent("TAB_SWITCH", "Student left the exam tab.", {
      trigger: "visibilitychange",
      hidden: true,
    });
    notifySecurityEvent("VISIBILITY_HIDDEN", "Exam tab became hidden.", {
      trigger: "visibilitychange",
    });
  } else {
    notifySecurityEvent("VISIBILITY_VISIBLE", "Exam tab became visible.", {
      trigger: "visibilitychange",
    });
    if (lockdownEnforced() && !document.fullscreenElement) {
      setLockdownStatus("Fullscreen needs resume", "warning");
      showFullscreenGuard();
      scheduleFullscreenResume("visibility_visible");
    }
  }
});

document.addEventListener("fullscreenchange", () => {
  if (lockdownEnforced() && !document.fullscreenElement) {
    setLockdownStatus("Fullscreen exited", "warning");
    setLockdownButtonText("Resume Fullscreen");
    showFullscreenGuard();
    notifySecurityEvent("FULLSCREEN_EXIT", "Student exited fullscreen mode.", {
      trigger: "fullscreenchange",
    });
    scheduleFullscreenResume("fullscreenchange");
  } else if (lockdownEnforced() && document.fullscreenElement) {
    setLockdownStatus("Fullscreen active", "success");
    setLockdownButtonText("Resume Fullscreen");
    hideFullscreenGuard();
    notifySecurityEvent("FULLSCREEN_ENTER", "Student entered fullscreen mode.", {
      trigger: "fullscreenchange",
    });
  }
});

document.addEventListener("keydown", blockRestrictedKeys);
document.addEventListener("contextmenu", (event) => {
  if (!lockdownStarted) return;
  event.preventDefault();
  notifySecurityEvent("BLOCKED_KEY", "Context menu blocked.", {
    trigger: "contextmenu",
  });
});

window.addEventListener("blur", () => {
  if (!lockdownEnforced()) return;
  setLockdownStatus("Window focus lost", "warning");
  notifySecurityEvent("FOCUS_LOST", "Exam window lost focus.", {
    trigger: "window_blur",
  });
  notifySecurityEvent("WINDOW_BLUR", "Browser window blurred.", {
    trigger: "window_blur",
  });
});

window.addEventListener("focus", () => {
  if (!lockdownEnforced()) return;
  notifySecurityEvent("FOCUS_RETURNED", "Exam window regained focus.", {
    trigger: "window_focus",
  });
  notifySecurityEvent("WINDOW_FOCUS", "Browser window focused.", {
    trigger: "window_focus",
  });
  if (!document.fullscreenElement) {
    setLockdownStatus("Fullscreen needs resume", "warning");
    showFullscreenGuard();
    scheduleFullscreenResume("window_focus");
  } else {
    setLockdownStatus("Fullscreen active", "success");
  }
});

window.addEventListener("pagehide", () => {
  if (!lockdownEnforced()) return;
  notifySecurityEvent(
    "PAGE_HIDE",
    "Exam page is being hidden or unloaded.",
    { trigger: "pagehide" },
    { keepalive: true }
  );
});

function markExamSubmitted() {
  examSubmitted = true;
  hideFullscreenGuard();
  setLockdownStatus("Exam submitted", "success");
  setLockdownButtonText("Fullscreen Complete");
}

document.addEventListener("DOMContentLoaded", () => {
  setLockdownStatus("Fullscreen inactive");
  document.querySelector("[data-lockdown-start]")?.addEventListener("click", startLockdown);
});

window.addEventListener("examguard:exam-submitted", markExamSubmitted);

window.ExamGuardLockdown = {
  start: startLockdown,
  isFullscreen: () => Boolean(document.fullscreenElement),
  hasStarted: () => lockdownStarted,
  markSubmitted: markExamSubmitted,
};
