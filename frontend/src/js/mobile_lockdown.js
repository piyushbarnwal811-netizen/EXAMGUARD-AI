/**
 * ExamGuard AI - Mobile Screen Lockdown & Integrity Guardrail
 * 
 * Capabilities:
 * 1. Screen Wake Lock API (keeps mobile display on indefinitely until submitted)
 * 2. Mobile Fullscreen Enforcement (locks out back navigation / home bar)
 * 3. App-Switching & Tab-Switching Detection (catches candidate minimizing browser / opening WhatsApp/AI)
 * 4. Hardware Back Button Trapping (prevents accidental exit)
 * 5. Screen Orientation & Touch Lockdown (blocks long-press context menu & text copying)
 */

(function () {
  let wakeLock = null;
  let mobileLockdownActive = false;
  let appSwitchCount = 0;
  const MAX_ALLOWED_SWITCHES = 3;

  function isMobileDevice() {
    const userAgent = navigator.userAgent || "";
    const isTouch = navigator.maxTouchPoints > 1;
    const isSmall = Math.min(window.innerWidth, window.innerHeight) <= 860;
    const isMobileUA = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(userAgent);
    return isMobileUA || (isTouch && isSmall);
  }

  // 1. Screen Wake Lock: Keep phone display awake indefinitely
  async function acquireScreenWakeLock() {
    if ("wakeLock" in navigator && !wakeLock) {
      try {
        wakeLock = await navigator.wakeLock.request("screen");
        wakeLock.addEventListener("release", () => {
          wakeLock = null;
        });
        console.log("ExamGuard: Screen WakeLock acquired (Display will stay ON)");
      } catch (err) {
        console.warn("ExamGuard: Screen WakeLock could not be acquired", err);
      }
    }
  }

  function releaseScreenWakeLock() {
    if (wakeLock) {
      wakeLock.release().catch(() => {});
      wakeLock = null;
    }
  }

  // 2. Mobile Fullscreen Mode
  async function requestMobileFullscreen() {
    const docEl = document.documentElement;
    try {
      if (docEl.requestFullscreen) {
        await docEl.requestFullscreen();
      } else if (docEl.webkitRequestFullscreen) {
        await docEl.webkitRequestFullscreen();
      }
      return true;
    } catch (_) {
      return false;
    }
  }

  // 3. Screen Orientation Lock
  async function lockMobileOrientation() {
    if (screen.orientation && screen.orientation.lock) {
      try {
        await screen.orientation.lock("portrait");
      } catch (_) {}
    }
  }

  // 4. Back-Button Trap (Android & iOS Navigation Trap)
  function trapBackButton() {
    history.pushState({ examguard_lock: true }, "", location.href);
    window.addEventListener("popstate", function (e) {
      if (mobileLockdownActive) {
        history.pushState({ examguard_lock: true }, "", location.href);
        triggerMobileViolation("BACK_NAVIGATION", "Hardware back button was pressed.");
        showMobileLockAlert("⚠️ Back Navigation Blocked! Use 'Finish Exam' button to submit.");
      }
    });
  }

  // 5. App Switch & Minimizing Detection
  function setupAppSwitchDetection() {
    document.addEventListener("visibilitychange", async function () {
      if (!mobileLockdownActive) return;

      if (document.visibilityState === "hidden") {
        appSwitchCount += 1;
        triggerMobileViolation(
          "TAB_SWITCH",
          `Candidate minimized browser or switched app (${appSwitchCount}/${MAX_ALLOWED_SWITCHES}).`
        );
      } else if (document.visibilityState === "visible") {
        // Re-acquire screen wake lock on return
        acquireScreenWakeLock();

        // Phone vibration alert
        if (navigator.vibrate) {
          navigator.vibrate([250, 100, 250]);
        }

        if (appSwitchCount >= MAX_ALLOWED_SWITCHES) {
          showTerminationOverlay();
        } else {
          showMobileLockAlert(
            `⚠️ Security Violation Logged! App switching detected (${appSwitchCount}/${MAX_ALLOWED_SWITCHES}). Return to exam now!`
          );
        }
      }
    });

    window.addEventListener("blur", function () {
      if (mobileLockdownActive && document.visibilityState === "visible") {
        triggerMobileViolation("WINDOW_BLUR", "Focus lost on mobile screen.");
      }
    });
  }

  // Helper: Trigger and Log Violation
  function triggerMobileViolation(type, message) {
    if (window.ExamGuardTracking?.sendEvent) {
      window.ExamGuardTracking.sendEvent(type, message, {
        is_mobile_device: true,
        app_switch_count: appSwitchCount,
        timestamp: new Date().toISOString(),
      });
    }
  }

  // 6. Mobile Security Notification Overlay
  function showMobileLockAlert(message) {
    let alertBox = document.getElementById("mobileLockToast");
    if (!alertBox) {
      alertBox = document.createElement("div");
      alertBox.id = "mobileLockToast";
      alertBox.className = "mobile-lock-toast";
      document.body.appendChild(alertBox);
    }
    alertBox.textContent = message;
    alertBox.classList.add("visible");
    setTimeout(() => {
      alertBox.classList.remove("visible");
    }, 4500);
  }

  function showTerminationOverlay() {
    const modal = document.createElement("div");
    modal.className = "mobile-lock-fullscreen-guard";
    modal.innerHTML = `
      <div class="mobile-lock-modal">
        <div class="mobile-lock-icon">🔒</div>
        <h2>Exam Locked &amp; Terminated</h2>
        <p>You have exceeded the maximum allowed app/tab switches (3/3). Your exam has been locked and automatically submitted for review.</p>
        <button type="button" class="btn-glow" id="btnLockedDone" style="width:100%;padding:14px;">
          View Submission Status
        </button>
      </div>
    `;
    document.body.appendChild(modal);
    modal.querySelector("#btnLockedDone")?.addEventListener("click", () => {
      window.location.reload();
    });
  }

  // 7. Fullscreen Guard Overlay if candidate drops out of fullscreen
  function ensureMobileFullscreenGuard() {
    let guard = document.querySelector("[data-mobile-fullscreen-guard]");
    if (guard) return guard;

    guard = document.createElement("div");
    guard.className = "mobile-lock-fullscreen-guard";
    guard.dataset.mobileFullscreenGuard = "true";
    guard.hidden = true;
    guard.innerHTML = `
      <div class="mobile-lock-modal">
        <div class="mobile-lock-icon">📱</div>
        <h2>Mobile Screen Locked</h2>
        <p>This exam runs under strict fullscreen lockdown. Tap below to re-enter fullscreen.</p>
        <button type="button" class="btn-glow" id="btnResumeMobileFS" style="width:100%;padding:14px;font-size:1rem;">
          🔒 Re-Enter Fullscreen Exam
        </button>
      </div>
    `;
    document.body.appendChild(guard);

    guard.querySelector("#btnResumeMobileFS")?.addEventListener("click", async () => {
      await requestMobileFullscreen();
      guard.hidden = true;
      acquireScreenWakeLock();
    });

    return guard;
  }

  function monitorMobileFullscreen() {
    const checkFS = () => {
      if (!mobileLockdownActive) return;
      const isFS = Boolean(document.fullscreenElement || document.webkitFullscreenElement);
      const guard = ensureMobileFullscreenGuard();
      if (!isFS) {
        guard.hidden = false;
        triggerMobileViolation("FULLSCREEN_EXIT", "Student exited mobile fullscreen.");
      } else {
        guard.hidden = true;
      }
    };

    document.addEventListener("fullscreenchange", checkFS);
    document.addEventListener("webkitfullscreenchange", checkFS);
  }

  // 8. Prevent long-press context menu and text selection
  function blockTouchCheating() {
    document.addEventListener("contextmenu", (e) => e.preventDefault());
    document.addEventListener("selectstart", (e) => {
      if (mobileLockdownActive) e.preventDefault();
    });
    window.addEventListener("beforeunload", (e) => {
      if (mobileLockdownActive) {
        e.preventDefault();
        e.returnValue = "Leaving this page will terminate your exam session.";
      }
    });
  }

  // 9. Public API: Activate Mobile Screen Lockdown
  async function activateMobileLockdown() {
    if (mobileLockdownActive) return;
    mobileLockdownActive = true;

    // Wake lock
    await acquireScreenWakeLock();

    // Fullscreen & Orientation
    await requestMobileFullscreen();
    await lockMobileOrientation();

    // Traps
    trapBackButton();
    setupAppSwitchDetection();
    monitorMobileFullscreen();
    blockTouchCheating();

    // Adapt Mobile SEB Gate: If SEB gate is open on mobile, automatically close it
    const sebGate = document.getElementById("sebGate");
    if (sebGate && isMobileDevice()) {
      sebGate.style.display = "none";
    }

    console.log("ExamGuard: Mobile Screen Lockdown ACTIVE ✅");
  }

  function deactivateMobileLockdown() {
    mobileLockdownActive = false;
    releaseScreenWakeLock();
  }

  // Expose to window
  window.ExamGuardMobileLockdown = {
    isMobile: isMobileDevice,
    activate: activateMobileLockdown,
    deactivate: deactivateMobileLockdown,
    isActive: () => mobileLockdownActive,
  };

  // Auto-init on student readiness or button tap
  document.addEventListener("DOMContentLoaded", () => {
    if (!isMobileDevice()) return;

    // Adapt SEB Gate for Mobile
    const sebGate = document.getElementById("sebGate");
    const launchSebBtn = document.getElementById("gateLaunchSEB");
    if (sebGate && launchSebBtn) {
      launchSebBtn.textContent = "📱 Start Proctored Mobile Exam (Lock Screen)";
      launchSebBtn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        activateMobileLockdown();
        sebGate.style.display = "none";
      });
    }

    // Auto-activate when precheck completes or exam starts
    document.addEventListener("examguard:precheck-complete", activateMobileLockdown);
    document.addEventListener("examguard:student-ready", activateMobileLockdown);

    // On user tap anywhere on the exam shell, activate fullscreen if pending
    document.addEventListener("click", function handleInitialMobileTouch() {
      if (isMobileDevice() && !mobileLockdownActive) {
        const isExamActive = Boolean(document.querySelector("[data-workspace]:not([hidden]), [data-mcq-workspace]:not([hidden])"));
        if (isExamActive) {
          activateMobileLockdown();
        }
      }
    }, { once: false });
  });
})();

