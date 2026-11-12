/**
 * ExamGuard AI - Candidate Invigilator Real-Time Client
 * Module 1: Live 1:50 Cockpit Connectivity, Micro-Stream Telemetry & Remote Interventions
 */

(function () {
  "use strict";

  const CLIENT_VERSION = "2.2.0";
  const HEARTBEAT_INTERVAL_MS = 8000; // 8s keeps 100+ concurrent WebSockets smooth while alerts push instantly
  const THUMBNAIL_WIDTH = 160;
  const THUMBNAIL_HEIGHT = 120;
  const THUMBNAIL_QUALITY = 0.5; // Compressed ~5-8KB WebP

  // Session Context Extraction
  function getQueryParam(name) {
    const params = new URLSearchParams(window.location.search);
    return params.get(name) || "";
  }

  function resolveWsBaseUrl() {
    const fallbackApi = "https://examguard-ai-317p.onrender.com/api";
    const configured = (window.EXAMGUARD_API_BASE || localStorage.getItem("examguard_api_base") || "").trim().replace(/\/$/, "");
    let apiUrl = configured;
    if (!apiUrl) {
      const isLocal = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1";
      apiUrl = isLocal ? "/api" : fallbackApi;
    }
    if (apiUrl.startsWith("/")) {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      return `${protocol}//${window.location.host}${apiUrl}`;
    }
    return apiUrl.replace(/^http:\/\//i, "ws://").replace(/^https:\/\//i, "wss://");
  }

  let examId = "exam_default";
  let sessionId = "";
  let rollNo = "";
  let candidateName = "";
  let candidateId = "";

  function refreshIdentity() {
    examId =
      getQueryParam("examId") ||
      getQueryParam("exam_id") ||
      getQueryParam("id") ||
      localStorage.getItem("examguard_exam_id") ||
      "exam_default";

    sessionId =
      getQueryParam("sessionId") ||
      getQueryParam("session_id") ||
      localStorage.getItem("examguard_session_id") ||
      `session_${Date.now().toString(36)}_${Math.random().toString(36).substring(2, 6)}`;
    localStorage.setItem("examguard_session_id", sessionId);

    rollNo =
      getQueryParam("roll") ||
      getQueryParam("roll_no") ||
      localStorage.getItem("examguard_roll_no") ||
      `Roll-${Math.floor(1000 + Math.random() * 9000)}`;

    candidateName =
      getQueryParam("name") ||
      localStorage.getItem("examguard_student_name") ||
      localStorage.getItem("examguard_candidate_name") ||
      "Student " + rollNo;

    candidateId =
      getQueryParam("candidateId") ||
      getQueryParam("user_id") ||
      localStorage.getItem("examguard_user_id") ||
      `cand_${sessionId.substring(0, 8)}`;
  }

  refreshIdentity();

  // State
  let ws = null;
  let heartbeatTimer = null;
  let reconnectTimer = null;
  let reconnectAttempts = 0;
  let isSessionFrozen = false;
  let isSessionTerminated = false;
  let lastCapturedThumbnail = null;
  let currentTrustScore = 100;
  let latestViolation = null;

  // Global Accessor for Proctoring Engine to update Trust Score and Violations
  window.ExamGuardInvigilatorClient = {
    setTrustScore: function (score) {
      currentTrustScore = Math.max(0, Math.min(100, Math.round(score)));
      const gauge = document.getElementById("trustScoreValue");
      if (gauge) gauge.textContent = `${currentTrustScore}%`;
    },
    setViolation: function (violationType, details) {
      latestViolation = violationType;
      // Deduct trust score progressively based on violation
      const penalties = {
        TAB_SWITCH: 10,
        MULTIPLE_FACES: 20,
        FACE_MISSING: 15,
        LOOKING_AWAY: 5,
        MOBILE_PHONE_DETECTED: 25,
        VOICE_ACTIVITY: 8,
        FULLSCREEN_EXIT: 15,
        SECONDARY_DISPLAY: 25,
      };
      const penalty = penalties[violationType] || 10;
      this.setTrustScore(currentTrustScore - penalty);
      if (violationType === "MOBILE_PHONE_DETECTED") {
        showMobilePhoneWarningModal(details);
      }
    },
    getTrustScore: function () {
      return currentTrustScore;
    },
    isFrozen: function () {
      return isSessionFrozen;
    },
    reconnectWithIdentity: function () {
      isSessionTerminated = false;
      reconnectAttempts = 0;
      clearTimeout(reconnectTimer);
      refreshIdentity();
      connectWebSocket();
    },
    disconnect: function () {
      isSessionTerminated = true;
      if (heartbeatTimer) clearInterval(heartbeatTimer);
      clearTimeout(reconnectTimer);
      if (ws) {
        try { ws.close(); } catch (_) {}
      }
    },
  };

  // Thumbnail capture from active camera preview
  function captureMicroThumbnail() {
    try {
      const video =
        document.querySelector("#cameraPreview") ||
        document.querySelector("video") ||
        document.querySelector("[data-camera-preview]");

      if (!video || video.readyState < 2 || !video.videoWidth) {
        return lastCapturedThumbnail;
      }

      const canvas = document.createElement("canvas");
      canvas.width = THUMBNAIL_WIDTH;
      canvas.height = THUMBNAIL_HEIGHT;
      const ctx = canvas.getContext("2d");
      if (!ctx) return lastCapturedThumbnail;

      // Center crop cover onto 160x120
      const vWidth = video.videoWidth;
      const vHeight = video.videoHeight;
      const aspect = vWidth / vHeight;
      const targetAspect = THUMBNAIL_WIDTH / THUMBNAIL_HEIGHT;

      let sx = 0, sy = 0, sw = vWidth, sh = vHeight;
      if (aspect > targetAspect) {
        sw = vHeight * targetAspect;
        sx = (vWidth - sw) / 2;
      } else {
        sh = vWidth / targetAspect;
        sy = (vHeight - sh) / 2;
      }

      ctx.drawImage(video, sx, sy, sw, sh, 0, 0, THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT);
      
      // Export as WebP or JPEG thumbnail (max ~6KB)
      const dataUrl = canvas.toDataURL("image/webp", THUMBNAIL_QUALITY);
      lastCapturedThumbnail = dataUrl;
      return dataUrl;
    } catch (e) {
      console.warn("[ExamGuard WS] Thumbnail capture error:", e);
      return lastCapturedThumbnail;
    }
  }

  // Interventions: Audio Warning
  function handleAudioAlert(payload) {
    const message = payload.message || "Please remain focused and keep your eyes centered on the screen.";
    console.warn("[ExamGuard WS] Remote Invigilator Audio Alert:", message);

    // 1. Play real audio if provided
    if (payload.audioBase64) {
      try {
        const audio = new Audio(payload.audioBase64);
        audio.play().catch(() => {});
      } catch (e) {
        console.warn("Base64 audio playback failed", e);
      }
    } else if (payload.audioBufferUrl) {
      try {
        const audio = new Audio(payload.audioBufferUrl);
        audio.play().catch(() => {});
      } catch (e) {
        console.warn("Audio URL playback failed", e);
      }
    }

    // 2. Play synthesized voice warning aloud
    if ("speechSynthesis" in window) {
      try {
        window.speechSynthesis.cancel(); // Stop any pending utterances
        const utterance = new SpeechSynthesisUtterance(message);
        utterance.rate = 1.0;
        utterance.pitch = 1.0;
        utterance.volume = 1.0;
        window.speechSynthesis.speak(utterance);
      } catch (e) {
        console.warn("SpeechSynthesis error:", e);
      }
    }

    // 3. Display High-Alert Toast UI
    showProctorToast("⚠️ Invigilator Warning", message, "urgent");
  }

  // Interventions: Session Freeze
  function handleSessionFreeze(isFrozen, reason) {
    isSessionFrozen = isFrozen;
    const modalId = "invigilatorFreezeOverlay";
    let modal = document.getElementById(modalId);

    if (isFrozen) {
      console.warn("[ExamGuard WS] Session FROZEN by invigilator. Reason:", reason);

      if (!modal) {
        modal = document.createElement("div");
        modal.id = modalId;
        modal.style.cssText = `
          position: fixed;
          inset: 0;
          z-index: 999999;
          background: rgba(10, 15, 29, 0.96);
          backdrop-filter: blur(12px);
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 24px;
          color: #f8fafc;
          font-family: 'Plus Jakarta Sans', system-ui, sans-serif;
        `;
        modal.innerHTML = `
          <div style="max-width: 520px; width: 100%; text-align: center; background: #0f172a; border: 1px solid rgba(239, 68, 68, 0.4); border-radius: 16px; padding: 36px 28px; box-shadow: 0 25px 50px -12px rgba(239, 68, 68, 0.25);">
            <div style="width: 64px; height: 64px; margin: 0 auto 18px; border-radius: 50%; background: rgba(239, 68, 68, 0.15); display: flex; align-items: center; justify-content: center; font-size: 32px; border: 1px solid rgba(239, 68, 68, 0.3);">
              ⏸️
            </div>
            <div style="display: inline-block; padding: 4px 12px; border-radius: 999px; background: rgba(239, 68, 68, 0.2); color: #f87171; font-size: 11px; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase; margin-bottom: 12px;">
              Session Temporarily Paused
            </div>
            <h2 style="font-size: 22px; font-weight: 700; margin: 0 0 10px; color: #ffffff;">Integrity Verification Check</h2>
            <p style="color: #94a3b8; font-size: 14px; line-height: 1.6; margin: 0 0 20px;">
              Your examination session has been temporarily paused by the invigilator for an academic integrity review.
            </p>
            <div style="background: rgba(15, 23, 42, 0.8); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 8px; padding: 12px; margin-bottom: 24px; text-align: left;">
              <span style="font-size: 11px; color: #64748b; font-weight: 600; text-transform: uppercase; display: block; margin-bottom: 4px;">Reason for pause:</span>
              <span style="font-size: 13px; color: #e2e8f0; font-family: 'JetBrains Mono', monospace;" id="freezeReasonText">${reason || "Live integrity verification"}</span>
            </div>
            <div style="display: flex; align-items: center; justify-content: center; gap: 8px; font-size: 12px; color: #64748b;">
              <span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #38bdf8; animation: pulse 1.5s infinite;"></span>
              Please look directly at your webcam while the invigilator inspects your session.
            </div>
          </div>
        `;
        document.body.appendChild(modal);
      } else {
        modal.style.display = "flex";
        const reasonEl = document.getElementById("freezeReasonText");
        if (reasonEl) reasonEl.textContent = reason || "Live integrity verification";
      }

      // Block background interactions
      const mainContainer = document.querySelector(".exam-shell") || document.querySelector("main");
      if (mainContainer) {
        mainContainer.style.pointerEvents = "none";
        mainContainer.style.filter = "blur(4px)";
      }
    } else {
      console.info("[ExamGuard WS] Session UN-FROZEN by invigilator.");
      if (modal) modal.style.display = "none";
      const mainContainer = document.querySelector(".exam-shell") || document.querySelector("main");
      if (mainContainer) {
        mainContainer.style.pointerEvents = "auto";
        mainContainer.style.filter = "none";
      }
      showProctorToast("✅ Exam Resumed", "Your exam session has been resumed by the invigilator.", "info");
    }
  }

  // Interventions: Force Terminate / Disqualification
  function handleForceTerminate(reason) {
    isSessionTerminated = true;
    console.error("[ExamGuard WS] Session FORCE TERMINATED by invigilator. Reason:", reason);

    // Stop heartbeat loop
    if (heartbeatTimer) clearInterval(heartbeatTimer);

    // Render permanent disqualification lockdown
    const termOverlay = document.createElement("div");
    termOverlay.id = "invigilatorTerminatedOverlay";
    termOverlay.style.cssText = `
      position: fixed;
      inset: 0;
      z-index: 9999999;
      background: #090d16;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 24px;
      color: #f8fafc;
      font-family: 'Plus Jakarta Sans', system-ui, sans-serif;
    `;
    termOverlay.innerHTML = `
      <div style="max-width: 520px; width: 100%; text-align: center; background: #0f172a; border: 2px solid #ef4444; border-radius: 20px; padding: 40px 32px; box-shadow: 0 0 60px rgba(239, 68, 68, 0.4);">
        <div style="width: 72px; height: 72px; margin: 0 auto 20px; border-radius: 50%; background: rgba(239, 68, 68, 0.2); display: flex; align-items: center; justify-content: center; font-size: 36px; border: 1px solid #ef4444;">
          ⛔
        </div>
        <div style="display: inline-block; padding: 6px 16px; border-radius: 999px; background: rgba(239, 68, 68, 0.25); color: #ef4444; font-size: 12px; font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 16px;">
          Session Disqualified & Locked
        </div>
        <h1 style="font-size: 26px; font-weight: 800; margin: 0 0 12px; color: #ffffff;">Assessment Terminated</h1>
        <p style="color: #cbd5e1; font-size: 14px; line-height: 1.6; margin: 0 0 24px;">
          This examination session has been permanently revoked by the invigilator due to violations of testing protocol.
        </p>
        <div style="background: rgba(0, 0, 0, 0.5); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 10px; padding: 14px; margin-bottom: 24px; text-align: left;">
          <span style="font-size: 11px; color: #f87171; font-weight: 700; text-transform: uppercase; display: block; margin-bottom: 4px;">Formal Reason:</span>
          <span style="font-size: 13px; color: #f1f5f9; font-family: 'JetBrains Mono', monospace;">${reason || "Academic integrity non-compliance"}</span>
        </div>
        <div style="font-size: 12px; color: #64748b; line-height: 1.5;">
          All telemetry, timestamps, violation logs, and webcam snapshots have been cryptographically preserved for administrative review.
        </div>
      </div>
    `;

    document.body.appendChild(termOverlay);

    // Disable all inputs & stop media streams
    try {
      const videos = document.querySelectorAll("video");
      videos.forEach((v) => {
        if (v.srcObject && typeof v.srcObject.getTracks === "function") {
          v.srcObject.getTracks().forEach((track) => track.stop());
        }
      });
    } catch (e) {}

    // Announce aloud
    if ("speechSynthesis" in window) {
      try {
        const u = new SpeechSynthesisUtterance("Your examination has been terminated by the invigilator.");
        window.speechSynthesis.speak(u);
      } catch (e) {}
    }
  }

  // Toast Display Helper
  function showProctorToast(title, desc, type = "info") {
    let toast = document.getElementById("proctorAlertToast");
    if (!toast) {
      toast = document.createElement("div");
      toast.id = "proctorAlertToast";
      toast.className = "proctor-hud-alert";
      toast.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 99999;
        display: flex;
        align-items: center;
        gap: 12px;
        background: #0f172a;
        color: #fff;
        padding: 14px 20px;
        border-radius: 12px;
        border: 1px solid rgba(239, 68, 68, 0.5);
        box-shadow: 0 10px 25px -5px rgba(0,0,0,0.5);
        font-family: 'Plus Jakarta Sans', system-ui, sans-serif;
        transition: all 0.3s ease;
      `;
      document.body.appendChild(toast);
    }

    const isUrgent = type === "urgent";
    toast.style.borderColor = isUrgent ? "#ef4444" : "#38bdf8";
    toast.style.boxShadow = isUrgent
      ? "0 0 20px rgba(239, 68, 68, 0.4)"
      : "0 0 20px rgba(56, 189, 248, 0.3)";
    toast.innerHTML = `
      <div style="font-size: 24px;">${isUrgent ? "⚠️" : "ℹ️"}</div>
      <div>
        <div style="font-size: 13px; font-weight: 700; color: ${isUrgent ? "#f87171" : "#38bdf8"}">${title}</div>
        <div style="font-size: 12px; color: #cbd5e1; margin-top: 2px;">${desc}</div>
      </div>
    `;

    toast.hidden = false;
    toast.style.display = "flex";

    // Auto dismiss after 6 seconds
    setTimeout(() => {
      if (toast && !isSessionFrozen && !isSessionTerminated) {
        toast.style.display = "none";
      }
    }, 6000);
  }

  // Mobile Phone High-Alert Security Modal for Student's Screen
  let phoneViolationStrikes = 0;
  function showMobilePhoneWarningModal(details = {}) {
    phoneViolationStrikes += 1;
    const modalId = "mobilePhoneWarningModal";
    let modal = document.getElementById(modalId);

    // 1. Play high-pitch security alert alarm via Web Audio API
    try {
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = "sawtooth";
      osc.frequency.setValueAtTime(880, audioCtx.currentTime);
      osc.frequency.setValueAtTime(440, audioCtx.currentTime + 0.15);
      osc.frequency.setValueAtTime(880, audioCtx.currentTime + 0.3);
      gain.gain.setValueAtTime(0.35, audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.65);
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      osc.start();
      osc.stop(audioCtx.currentTime + 0.65);
    } catch (e) {}

    // 2. Vibrate candidate device
    if (navigator.vibrate) {
      try {
        navigator.vibrate([300, 150, 300, 150, 600]);
      } catch (e) {}
    }

    // 3. Audio warning aloud
    if ("speechSynthesis" in window) {
      try {
        window.speechSynthesis.cancel();
        const u = new SpeechSynthesisUtterance("Warning! Mobile phone detected in exam area. Remove it immediately.");
        u.rate = 1.0;
        window.speechSynthesis.speak(u);
      } catch (e) {}
    }

    // 4. Create or reveal Modal Overlay
    if (!modal) {
      modal = document.createElement("div");
      modal.id = modalId;
      modal.style.cssText = `
        position: fixed;
        inset: 0;
        z-index: 99999999;
        background: rgba(5, 9, 20, 0.96);
        backdrop-filter: blur(16px);
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 20px;
        color: #f8fafc;
        font-family: 'Plus Jakarta Sans', system-ui, sans-serif;
      `;
      document.body.appendChild(modal);
    }

    modal.innerHTML = `
      <div style="max-width: 480px; width: 100%; text-align: center; background: #0f172a; border: 2px solid #ef4444; border-radius: 20px; padding: 32px 24px; box-shadow: 0 0 50px rgba(239, 68, 68, 0.45);">
        <div style="width: 72px; height: 72px; margin: 0 auto 16px; border-radius: 50%; background: rgba(239, 68, 68, 0.2); display: flex; align-items: center; justify-content: center; font-size: 36px; border: 1.5px solid #ef4444;">
          📱🚫
        </div>
        
        <div style="display: inline-block; padding: 5px 14px; border-radius: 999px; background: rgba(239, 68, 68, 0.25); color: #ef4444; font-size: 11px; font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 12px;">
          Security Alert • Strike ${phoneViolationStrikes} / 3
        </div>

        <h2 style="font-size: 20px; font-weight: 800; margin: 0 0 10px; color: #ffffff;">
          ⚠️ दूसरा मोबाइल फोन पकड़ा गया!
        </h2>
        
        <p style="color: #cbd5e1; font-size: 13.5px; line-height: 1.6; margin: 0 0 16px;">
          Aapke camera me <strong>dusra mobile phone</strong> detect hua hai. Exam ke dauran kisi dusre phone ya screen se cheating karna sakht mana hai.
        </p>

        <div style="background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 10px; padding: 12px; margin-bottom: 22px; text-align: left; font-size: 12px; color: #fca5a5; line-height: 1.5;">
          🚨 <strong>Live Invigilator Notified:</strong> Yeh violation snapshot ke saath Examiner (Admin) ko turant report kar diya gaya hai. Agli baar phone dikhne par exam terminate kar diya jayega.
        </div>

        <button type="button" id="btnDismissPhoneWarning" style="width: 100%; padding: 14px; background: linear-gradient(135deg, #ef4444, #dc2626); color: #fff; border: none; border-radius: 10px; font-weight: 700; font-size: 15px; cursor: pointer; box-shadow: 0 4px 15px rgba(239, 68, 68, 0.4);">
          ✓ मैंने फोन हटा दिया है - परीक्षा जारी रखें
        </button>
      </div>
    `;

    modal.style.display = "flex";

    // Immediate heartbeat to admin
    latestViolation = "MOBILE_PHONE_DETECTED";
    sendHeartbeat();

    document.getElementById("btnDismissPhoneWarning")?.addEventListener("click", () => {
      modal.style.display = "none";
      latestViolation = null;
    });
  }

  // Heartbeat sender (every 4.5 seconds)
  function sendHeartbeat() {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    if (isSessionTerminated) return;

    const thumbnail = captureMicroThumbnail();

    const payload = {
      type: "CANDIDATE_HEARTBEAT",
      sessionId: sessionId,
      candidateId: candidateId,
      rollNo: rollNo,
      name: candidateName,
      trustScore: currentTrustScore,
      latestViolation: latestViolation,
      thumbnailBase64: thumbnail,
      timestamp: new Date().toISOString(),
    };

    try {
      ws.send(JSON.stringify(payload));
    } catch (e) {
      console.warn("[ExamGuard WS] Failed to dispatch heartbeat:", e);
    }
  }

  // Connect WebSocket to FastAPI Hub
  function connectWebSocket() {
    if (isSessionTerminated) return;
    clearTimeout(reconnectTimer);
    if (heartbeatTimer) clearInterval(heartbeatTimer);
    if (ws) {
      try {
        ws.onclose = null;
        ws.onerror = null;
        ws.close();
      } catch (_) {}
      ws = null;
    }

    refreshIdentity();

    const wsBase = resolveWsBaseUrl();
    const wsUrl = `${wsBase}/ws/invigilator/${encodeURIComponent(examId)}?role=candidate&session_id=${encodeURIComponent(sessionId)}&candidate_id=${encodeURIComponent(candidateId)}&roll_no=${encodeURIComponent(rollNo)}&name=${encodeURIComponent(candidateName)}`;

    try {
      const socket = new WebSocket(wsUrl);
      ws = socket;

      socket.onopen = function () {
        console.info(`[ExamGuard WS] Candidate connected to invigilator cockpit (Session: ${sessionId})`);
        reconnectAttempts = 0;

        // Send initial heartbeat immediately
        sendHeartbeat();

        // Start periodic micro-stream polling
        if (heartbeatTimer) clearInterval(heartbeatTimer);
        heartbeatTimer = setInterval(sendHeartbeat, HEARTBEAT_INTERVAL_MS);
      };

      socket.onmessage = function (event) {
        try {
          const msg = JSON.parse(event.data);
          const type = msg.type;

          if (type === "TRIGGER_AUDIO_ALERT") {
            handleAudioAlert(msg);
          } else if (type === "TOGGLE_SESSION_FREEZE") {
            handleSessionFreeze(Boolean(msg.isFrozen), msg.reason);
          } else if (type === "FORCE_TERMINATE") {
            handleForceTerminate(msg.reason);
          }
        } catch (e) {
          console.error("[ExamGuard WS] Failed to process incoming message:", e);
        }
      };

      socket.onclose = function () {
        if (ws !== socket) return;
        if (heartbeatTimer) clearInterval(heartbeatTimer);
        if (!isSessionTerminated) {
          // Reconnect with backoff
          const delay = Math.min(10000, 2000 * Math.pow(1.5, reconnectAttempts));
          reconnectAttempts += 1;
          console.warn(`[ExamGuard WS] Disconnected. Reconnecting in ${Math.round(delay / 1000)}s...`);
          clearTimeout(reconnectTimer);
          reconnectTimer = setTimeout(connectWebSocket, delay);
        }
      };

      socket.onerror = function (err) {
        console.warn("[ExamGuard WS] Socket error:", err);
        try { socket.close(); } catch (_) {}
      };
    } catch (e) {
      console.warn("[ExamGuard WS] Connection exception:", e);
    }
  }

  document.addEventListener("examguard:student-ready", function () {
    window.ExamGuardInvigilatorClient.reconnectWithIdentity();
  });

  function initInvigilatorClient() {
    const onboardingGate = document.getElementById("onboardingGate");
    if (onboardingGate && onboardingGate.style.display !== "none") {
      // Wait for student onboarding completion on standalone MCQ portal
      return;
    }
    connectWebSocket();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initInvigilatorClient);
  } else {
    initInvigilatorClient();
  }
})();
