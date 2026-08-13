const cameraState = {
  stream: null,
  autoStartAttempted: false,
  status: "idle",
};

const cameraQs = (selector) => document.querySelector(selector);

function cameraStatusText(message, type = "") {
  const status = cameraQs("[data-camera-status]");
  const indicator = cameraQs("[data-camera-indicator]");
  if (status) status.textContent = message;
  if (indicator) indicator.className = `status-pill ${type}`.trim();
  window.dispatchEvent(
    new CustomEvent("examguard:camera-status-change", {
      detail: { status: cameraState.status, message },
    })
  );
}

function setCameraControls(running) {
  const startButton = cameraQs("[data-camera-start]");
  const stopButton = cameraQs("[data-camera-stop]");
  if (startButton) startButton.disabled = running;
  if (stopButton) stopButton.disabled = !running;
}

function cameraDetails(extra = {}) {
  const tracks = cameraState.stream?.getVideoTracks?.() || [];
  const settings = tracks[0]?.getSettings?.() || {};
  return {
    camera_status: cameraState.status,
    track_count: tracks.length,
    width: settings.width,
    height: settings.height,
    frame_rate: settings.frameRate,
    ...extra,
  };
}

function reportCameraEvent(eventType, message, details = {}, options = {}) {
  if (!window.ExamGuardTracking?.sendEvent) return;
  window.ExamGuardTracking.sendEvent(
    eventType,
    message,
    cameraDetails(details),
    options
  ).catch(() => undefined);
}

function cameraErrorMessage(error) {
  if (error?.name === "NotAllowedError" || error?.name === "SecurityError") {
    return "Camera permission denied.";
  }
  if (error?.name === "NotFoundError" || error?.name === "OverconstrainedError") {
    return "No usable camera found.";
  }
  if (error?.name === "NotReadableError") {
    return "Camera is already in use.";
  }
  return "Camera could not start.";
}

async function probeCameraPermission() {
  if (!navigator.permissions?.query) return;

  try {
    const permission = await navigator.permissions.query({ name: "camera" });
    const update = () => {
      if (cameraState.stream) return;
      if (permission.state === "denied") {
        cameraState.status = "denied";
        cameraStatusText("Camera permission denied", "warning");
      } else if (permission.state === "granted") {
        cameraStatusText("Camera ready to start");
      } else {
        cameraStatusText("Camera permission needed");
      }
    };
    permission.addEventListener?.("change", update);
    update();
  } catch {
    cameraStatusText("Camera permission needed");
  }
}

function bindTrackEndHandlers(stream) {
  stream.getVideoTracks().forEach((track) => {
    track.addEventListener("ended", () => {
      if (!cameraState.stream) return;
      cameraState.stream = null;
      cameraState.status = "ended";
      const video = cameraQs("#cameraPreview");
      if (video) video.srcObject = null;
      setCameraControls(false);
      cameraStatusText("Camera stopped by device", "warning");
      reportCameraEvent("CAMERA_TRACK_ENDED", "Camera video track ended.");
    });
  });
}

async function startCamera(options = {}) {
  const video = cameraQs("#cameraPreview");
  if (!video || cameraState.stream) return cameraState.stream;

  if (!navigator.mediaDevices?.getUserMedia) {
    cameraState.status = "unavailable";
    cameraStatusText("Camera unavailable", "warning");
    reportCameraEvent("CAMERA_UNAVAILABLE", "Browser does not support camera access.");
    return null;
  }

  cameraState.status = "requesting";
  cameraStatusText("Requesting camera permission");
  reportCameraEvent("CAMERA_PERMISSION_REQUESTED", "Camera permission requested.", {
    requested_by: options.requestedBy || "manual",
  });

  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: false,
      video: {
        facingMode: "user",
        width: { ideal: 640 },
        height: { ideal: 480 },
      },
    });

    cameraState.stream = stream;
    cameraState.status = "running";
    video.srcObject = stream;
    await video.play().catch(() => undefined);
    bindTrackEndHandlers(stream);
    setCameraControls(true);
    cameraStatusText("Camera active", "success");
    reportCameraEvent("CAMERA_STARTED", "Camera stream started.", {
      requested_by: options.requestedBy || "manual",
    });
    return stream;
  } catch (error) {
    cameraState.stream = null;
    cameraState.status = "error";
    const message = cameraErrorMessage(error);
    setCameraControls(false);
    cameraStatusText(message, "warning");
    reportCameraEvent(
      message.includes("denied") ? "CAMERA_PERMISSION_DENIED" : "CAMERA_ERROR",
      message,
      {
        error_name: error?.name || "UnknownError",
        requested_by: options.requestedBy || "manual",
      }
    );
    return null;
  }
}

function stopCamera(reason = "manual_stop", options = {}) {
  if (!cameraState.stream) return;

  const stream = cameraState.stream;
  cameraState.stream = null;
  stream.getTracks().forEach((track) => track.stop());

  const video = cameraQs("#cameraPreview");
  if (video) video.srcObject = null;

  cameraState.status = "stopped";
  setCameraControls(false);
  cameraStatusText("Camera stopped", reason === "manual_stop" ? "" : "warning");
  reportCameraEvent("CAMERA_STOPPED", "Camera stream stopped.", { reason }, options);
}

function autoStartCamera() {
  if (cameraState.autoStartAttempted || !cameraQs("[data-camera-panel]")) return;
  if (window.ExamGuardExamGate?.requiresPrecheck?.()) return;
  cameraState.autoStartAttempted = true;
  startCamera({ requestedBy: "student_ready" });
}

document.addEventListener("examguard:student-ready", autoStartCamera);

document.addEventListener("DOMContentLoaded", () => {
  if (!cameraQs("[data-camera-panel]")) return;

  cameraStatusText("Camera permission needed");
  setCameraControls(false);
  probeCameraPermission();

  cameraQs("[data-camera-start]")?.addEventListener("click", () => {
    startCamera({ requestedBy: "manual" });
  });
  cameraQs("[data-camera-stop]")?.addEventListener("click", () => {
    stopCamera("manual_stop");
  });

  if (localStorage.getItem("examguard_token")) {
    autoStartCamera();
  }
});

window.addEventListener("pagehide", () => {
  stopCamera("pagehide", { keepalive: true });
});

window.ExamGuardCamera = {
  start: startCamera,
  stop: stopCamera,
  status: () => cameraState.status,
};
