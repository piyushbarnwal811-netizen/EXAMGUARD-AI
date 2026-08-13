const precheckState = {
  system: false,
  camera: false,
  location: false,
  fullscreen: false,
  complete: false,
  running: false,
};

const precheckQs = (selector) => document.querySelector(selector);

function setPrecheckPanelVisible(visible) {
  const panel = precheckQs("[data-precheck-panel]");
  if (panel) panel.hidden = !visible;
}

function setPrecheckButtonBusy(busy) {
  const button = precheckQs("[data-precheck-start]");
  if (!button) return;
  button.disabled = busy;
  button.textContent = busy ? "Checking..." : "Start Checks";
}

function setPrecheckCopy(message, type = "") {
  const copy = precheckQs("[data-precheck-copy]");
  if (!copy) return;
  copy.className = `muted ${type}`.trim();
  copy.textContent = message;
}

function markPrecheckItem(name, state, message) {
  const item = precheckQs(`[data-precheck-${name}]`);
  if (!item) return;

  item.className = `precheck-item ${state}`.trim();
  const detail = item.querySelector("span:last-child");
  if (detail) detail.textContent = message;
}

function canUseLocalStorage() {
  try {
    const key = "examguard_precheck_test";
    localStorage.setItem(key, "1");
    localStorage.removeItem(key);
    return true;
  } catch {
    return false;
  }
}

function checkSystemCompatibility() {
  const missing = [];
  if (!window.fetch) missing.push("network");
  if (!canUseLocalStorage()) missing.push("storage");
  if (!navigator.mediaDevices?.getUserMedia) missing.push("camera");
  if (!navigator.geolocation) missing.push("location");
  if (!document.documentElement.requestFullscreen) missing.push("fullscreen");

  precheckState.system = missing.length === 0;
  markPrecheckItem(
    "system",
    precheckState.system ? "success" : "warning",
    precheckState.system ? "Compatible" : `Missing ${missing.join(", ")}`
  );
  return precheckState.system;
}

async function checkCameraPermission() {
  markPrecheckItem("camera", "", "Requesting");
  const stream = await window.ExamGuardCamera?.start?.({ requestedBy: "precheck" });
  precheckState.camera = Boolean(stream);
  markPrecheckItem(
    "camera",
    precheckState.camera ? "success" : "warning",
    precheckState.camera ? "Granted" : "Required"
  );
  return precheckState.camera;
}

async function checkLocationPermission() {
  markPrecheckItem("location", "", "Requesting");
  const shared = await window.ExamGuardTracking?.sendLocation?.({
    requestedBy: "precheck",
  });
  precheckState.location = Boolean(shared);
  markPrecheckItem(
    "location",
    precheckState.location ? "success" : "warning",
    precheckState.location ? "Shared" : "Required"
  );
  return precheckState.location;
}

async function checkFullscreen() {
  markPrecheckItem("fullscreen", "", "Starting");
  const started = await window.ExamGuardLockdown?.start?.({ requestedBy: "precheck" });
  precheckState.fullscreen = Boolean(started || document.fullscreenElement);
  markPrecheckItem(
    "fullscreen",
    precheckState.fullscreen ? "success" : "warning",
    precheckState.fullscreen ? "Active" : "Required"
  );
  return precheckState.fullscreen;
}

function finishPrecheck() {
  precheckState.complete = true;
  setPrecheckPanelVisible(false);
  setPrecheckCopy("Checks complete.", "success");
  document.dispatchEvent(new CustomEvent("examguard:precheck-complete"));
}

async function startPrecheck() {
  if (precheckState.running || precheckState.complete) return precheckState.complete;

  precheckState.running = true;
  setPrecheckButtonBusy(true);
  setPrecheckCopy("Checking system, camera, location, and fullscreen.");

  try {
    const systemOk = checkSystemCompatibility();
    if (!systemOk) {
      setPrecheckCopy("This browser cannot start the secure exam.", "warning");
      return false;
    }

    const cameraOk = await checkCameraPermission();
    const locationOk = await checkLocationPermission();
    const fullscreenOk = cameraOk && locationOk ? await checkFullscreen() : false;

    if (systemOk && cameraOk && locationOk && fullscreenOk) {
      finishPrecheck();
      return true;
    }

    setPrecheckCopy("All permissions are required before the contest opens.", "warning");
    return false;
  } finally {
    precheckState.running = false;
    setPrecheckButtonBusy(false);
  }
}

function showPrecheckGate() {
  if (precheckState.complete) return;
  setPrecheckPanelVisible(true);
  checkSystemCompatibility();
}

document.addEventListener("DOMContentLoaded", () => {
  if (!precheckQs("[data-precheck-panel]")) return;
  precheckQs("[data-precheck-start]")?.addEventListener("click", startPrecheck);
});

window.ExamGuardExamGate = {
  requiresPrecheck: () => Boolean(precheckQs("[data-precheck-panel]")),
  isComplete: () => precheckState.complete,
  show: showPrecheckGate,
  start: startPrecheck,
};
