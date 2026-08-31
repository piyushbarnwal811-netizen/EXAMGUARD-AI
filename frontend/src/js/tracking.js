const TRACKING_API_BASE = window.EXAMGUARD_API_BASE || "/api";
const trackingState = {
  locationStatus: "idle",
  mobileDeviceReported: false,
};

function trackingAuthHeaders() {
  const token = localStorage.getItem("examguard_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function currentTrackingContext(extraDetails = {}) {
  const timezone =
    Intl.DateTimeFormat?.().resolvedOptions?.().timeZone || "unknown";
  return {
    page_url: window.location.href,
    visibility_state: document.visibilityState,
    fullscreen_active: Boolean(document.fullscreenElement),
    client_local_timestamp: new Date().toString(),
    client_timezone: timezone,
    client_timezone_offset_minutes: new Date().getTimezoneOffset(),
    ...extraDetails,
  };
}

async function sendTrackingEvent(eventType, message = "", details = {}, options = {}) {
  const token = localStorage.getItem("examguard_token");
  if (!token) return null;

  const payload = {
    event_type: eventType,
    message,
    client_timestamp: new Date().toISOString(),
    ...(options.fields || {}),
    details: currentTrackingContext(details),
  };

  const response = await fetch(`${TRACKING_API_BASE}/tracking/events`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...trackingAuthHeaders(),
    },
    body: JSON.stringify(payload),
    keepalive: Boolean(options.keepalive),
  }).catch(() => null);

  if (!response?.ok) return null;
  return response.json().catch(() => null);
}

async function checkIpStatus() {
  const status = document.querySelector("[data-ip-status]");
  if (!status) return;

  try {
    const response = await fetch(`${TRACKING_API_BASE}/tracking/geofence/check`, {
      headers: trackingAuthHeaders(),
    });
    const data = await response.json();
    status.textContent = `IP: ${data.ip} (${data.allowed ? "allowed" : "blocked"})`;
  } catch {
    status.textContent = "IP check unavailable.";
  }
}

function detectMobileDevice() {
  const userAgent = navigator.userAgent || "";
  const userAgentData = navigator.userAgentData || {};
  const isMobileUserAgent =
    Boolean(userAgentData.mobile) ||
    /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(userAgent);
  const hasTouch = navigator.maxTouchPoints > 1;
  const smallViewport = Math.min(window.innerWidth, window.innerHeight) <= 820;

  return {
    is_mobile_device: Boolean(isMobileUserAgent || (hasTouch && smallViewport)),
    user_agent_mobile: Boolean(isMobileUserAgent),
    touch_points: navigator.maxTouchPoints || 0,
    viewport_width: window.innerWidth,
    viewport_height: window.innerHeight,
    screen_width: window.screen?.width,
    screen_height: window.screen?.height,
    device_pixel_ratio: window.devicePixelRatio || 1,
    platform: navigator.platform || "",
  };
}

function isExamPage() {
  return Boolean(
    document.querySelector("[data-coding-contest], [data-question-list]")
  );
}

function shouldBlockMobileExam() {
  return isExamPage() && detectMobileDevice().is_mobile_device;
}

function renderMobileBlocker() {
  let blocker = document.querySelector("[data-mobile-blocker]");
  if (blocker) return blocker;

  blocker = document.createElement("section");
  blocker.className = "mobile-blocker";
  blocker.dataset.mobileBlocker = "true";
  blocker.innerHTML = `
    <div class="mobile-blocker-panel">
      <p class="eyebrow">Device Blocked</p>
      <h1>Desktop Required</h1>
      <p class="muted">This exam cannot be opened on mobile or tablet devices. Please use a laptop or desktop computer.</p>
    </div>
  `;
  document.body.appendChild(blocker);
  return blocker;
}

function blockMobileExam(trigger = "mobile_gate") {
  if (!shouldBlockMobileExam()) return false;

  renderMobileBlocker();
  reportMobileDeviceUse(trigger, "MOBILE_DEVICE_BLOCKED");
  return true;
}

function reportMobileDeviceUse(
  trigger = "student_ready",
  eventType = "MOBILE_DEVICE_DETECTED"
) {
  if (trackingState.mobileDeviceReported) return;

  const device = detectMobileDevice();
  if (!device.is_mobile_device) return;

  trackingState.mobileDeviceReported = true;
  sendTrackingEvent(
    eventType,
    eventType === "MOBILE_DEVICE_BLOCKED"
      ? "Mobile or tablet exam access was blocked."
      : "Student opened or used the exam on a mobile device.",
    {
      trigger,
      detected_at: new Date().toISOString(),
      ...device,
    },
    { keepalive: true }
  );
}

function setLocationStatus(message, type = "") {
  const status = document.querySelector("[data-location-status]");
  const indicator = document.querySelector("[data-location-indicator]");
  if (status) status.textContent = message;
  if (indicator) indicator.className = `status-pill ${type}`.trim();
}

function locationErrorMessage(error) {
  if (error?.code === 1) return "Location permission denied";
  if (error?.code === 2) return "Location unavailable";
  if (error?.code === 3) return "Location timed out";
  return "Location could not be shared";
}

function updateLocationState(status, message, type = "") {
  trackingState.locationStatus = status;
  setLocationStatus(message, type);
  window.dispatchEvent(
    new CustomEvent("examguard:location-status-change", {
      detail: { status, message },
    })
  );
}

function sendLocation(options = {}) {
  if (!navigator.geolocation) {
    updateLocationState("unavailable", "Location unavailable", "warning");
    sendTrackingEvent("LOCATION_UNAVAILABLE", "Browser does not support geolocation.", {
      requested_by: options.requestedBy || "manual",
    });
    return Promise.resolve(false);
  }

  updateLocationState("requesting", "Requesting location");
  sendTrackingEvent("LOCATION_PERMISSION_REQUESTED", "Location permission requested.", {
    requested_by: options.requestedBy || "manual",
  });

  return new Promise((resolve) => {
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const location = `${position.coords.latitude},${position.coords.longitude}`;
        updateLocationState("shared", "Location shared", "success");
        sendTrackingEvent(
          "LOCATION",
          "Student shared browser geolocation.",
          {
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
            accuracy: position.coords.accuracy,
            location,
            requested_by: options.requestedBy || "manual",
          },
          {
            fields: {
              latitude: position.coords.latitude,
              longitude: position.coords.longitude,
              location,
            },
          }
        ).finally(() => resolve(true));
      },
      (error) => {
        const message = locationErrorMessage(error);
        updateLocationState("denied", message, "warning");
        sendTrackingEvent("LOCATION_PERMISSION_DENIED", message, {
          code: error?.code,
          requested_by: options.requestedBy || "manual",
        }).finally(() => resolve(false));
      },
      {
        enableHighAccuracy: true,
        timeout: 15000,
        maximumAge: 0,
      }
    );
  });
}

window.ExamGuardTracking = {
  authHeaders: trackingAuthHeaders,
  blockMobileExam,
  checkIpStatus,
  detectMobileDevice,
  reportMobileDeviceUse,
  shouldBlockMobileExam,
  sendEvent: sendTrackingEvent,
  sendLocation,
  locationStatus: () => trackingState.locationStatus,
};

document.addEventListener("DOMContentLoaded", () => {
  checkIpStatus();
  setLocationStatus("Location permission needed");
  document.querySelector("[data-location-send]")?.addEventListener("click", () => {
    sendLocation({ requestedBy: "manual" });
  });
  if (!blockMobileExam("dom_content_loaded")) {
    reportMobileDeviceUse("dom_content_loaded");
  }
});

document.addEventListener("examguard:student-ready", () => {
  blockMobileExam("student_ready");
});
