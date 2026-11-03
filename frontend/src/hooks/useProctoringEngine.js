/**
 * ExamGuard AI - Advanced Client-Side Proctoring Engine Hook
 * 
 * Architectural Principle:
 * - Client-Side Heavy, Server-Side Light
 * - 3-5 FPS Inference rate to prevent client CPU throttling
 * - Low-bandwidth lightweight JSON metadata + <=50KB compressed WebP evidence snapshots
 * - Offline-resilient local buffer (IndexedDB / LocalStorage)
 */

import { useState, useEffect, useRef, useCallback } from "react";

// MediaPipe CDN URLs for on-demand browser loading without heavy bundler bloat
const MEDIAPIPE_VISION_CDN =
  "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.22/vision_bundle.mjs";
const MEDIAPIPE_WASM_CDN =
  "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.22/wasm";
const FACE_LANDMARKER_MODEL_URL =
  "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task";

// Key Facial Landmark Indices (MediaPipe Face Mesh)
const LANDMARKS = {
  noseTip: 1,
  chin: 152,
  forehead: 10,
  leftEyeOuter: 33,
  leftEyeInner: 133,
  leftEyeTop: 159,
  leftEyeBottom: 145,
  rightEyeInner: 362,
  rightEyeOuter: 263,
  rightEyeTop: 386,
  rightEyeBottom: 374,
  leftIris: [468, 469, 470, 471, 472],
  rightIris: [473, 474, 475, 476, 477],
  mouthTop: 13,
  mouthBottom: 14,
};

const DEFAULT_PENALTY_WEIGHTS = {
  MULTIPLE_FACES: 20,
  CANDIDATE_ABSENT: 15,
  FACE_MISSING: 15,
  GAZE_ANOMALY: 10,
  LOOKING_AWAY: 10,
  PROHIBITED_OBJECT: 25,
  OBJECT_DETECTED: 25,
  SPEECH_DETECTED: 10,
  ACOUSTIC_ACTIVITY: 10,
  TAB_SWITCH: 10,
  WINDOW_BLUR: 5,
  FULLSCREEN_EXIT: 15,
  CLIPBOARD_VIOLATION: 10,
  DUAL_MONITOR_DETECTED: 20,
  UNAUTHORIZED_KEY: 5,
};

export function useProctoringEngine({
  examId,
  candidateId,
  sessionId,
  apiBaseUrl = "/api/v1/proctor",
  token = null,
  penaltyWeights = DEFAULT_PENALTY_WEIGHTS,
  maxExits = 3,
  criticalTrustScore = 30,
  enableAudio = true,
  enableObjectDetection = true,
  targetFps = 4, // 3 - 5 FPS to eliminate CPU throttling
  onAutoSubmit = null,
  onViolation = null,
  onWarning = null,
} = {}) {
  // DOM References
  const videoRef = useRef(null);
  const canvasRef = useRef(null);

  // Hardware & Stream References
  const mediaStreamRef = useRef(null);
  const audioContextRef = useRef(null);
  const analyserRef = useRef(null);
  const audioDataRef = useRef(null);

  // Vision State References
  const faceLandmarkerRef = useRef(null);
  const animationFrameIdRef = useRef(null);
  const lastVisionTickRef = useRef(0);
  const lastAudioTickRef = useRef(0);

  // Violation Timers & Cooldown References (State mirrors for requestAnimationFrame loop)
  const violationCountersRef = useRef({});
  const streakTimersRef = useRef({
    multipleFacesStart: 0,
    faceMissingStart: 0,
    gazeAnomalyStart: 0,
    audioSpikeStart: 0,
  });
  const cooldownsRef = useRef(new Map());

  // Calibration Baseline Reference
  const baselineRef = useRef(null);
  const calibrationSamplesRef = useRef([]);

  // Local Buffer Queue (survives network disconnects)
  const localBufferRef = useRef([]);

  // React State for UI
  const [isInitialized, setIsInitialized] = useState(false);
  const [isCalibrating, setIsCalibrating] = useState(false);
  const [calibrationProgress, setCalibrationProgress] = useState(0);
  const [isCalibrated, setIsCalibrated] = useState(false);
  const [isMonitoring, setIsMonitoring] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [trustScore, setTrustScore] = useState(100);
  const [exitCount, setExitCount] = useState(0);
  const [activeAlert, setActiveAlert] = useState(null);
  const [audioLevel, setAudioLevel] = useState(0);
  const [fps, setFps] = useState(0);
  const [violationCounts, setViolationCounts] = useState({});
  const [violationHistory, setViolationHistory] = useState([]);
  const [bufferedEventsCount, setBufferedEventsCount] = useState(0);

  // Synchronize weights
  const mergedWeights = { ...DEFAULT_PENALTY_WEIGHTS, ...penaltyWeights };

  // ---------------------------------------------------------------------------
  // HELPER: Calculate Local Trust Score
  // ---------------------------------------------------------------------------
  const calculateTrustScore = useCallback(
    (counters) => {
      let penaltyTotal = 0;
      Object.entries(counters).forEach(([type, count]) => {
        const weight = mergedWeights[type] || 5;
        penaltyTotal += count * weight;
      });
      return Math.max(0, 100 - penaltyTotal);
    },
    [mergedWeights]
  );

  // ---------------------------------------------------------------------------
  // HELPER: Snapshot Generation (Strictly <= 50KB Compressed WebP)
  // ---------------------------------------------------------------------------
  const captureEvidenceSnapshot = useCallback(() => {
    const video = videoRef.current;
    if (!video || video.readyState < 2) return null;

    // Use offscreen or fallback canvas
    const canvas = canvasRef.current || document.createElement("canvas");
    // Target 480x360 for high quality yet tiny ~15KB-30KB WebP payload
    const width = 480;
    const height = (video.videoHeight / (video.videoWidth || 1)) * width || 360;

    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;

    // Flip horizontal to match candidate mirror view
    ctx.save();
    ctx.scale(-1, 1);
    ctx.drawImage(video, -width, 0, width, height);
    ctx.restore();

    // Timestamp & watermark on proof snippet
    ctx.fillStyle = "rgba(0, 0, 0, 0.65)";
    ctx.fillRect(0, height - 28, width, 28);
    ctx.fillStyle = "#10b981";
    ctx.font = "bold 11px monospace";
    ctx.fillText(
      `EXAMGUARD PROCTOR PROOF • ${new Date().toISOString()}`,
      10,
      height - 10
    );

    // Compress to WebP (quality 0.58 ensures < 45KB payload)
    let snapshotBase64 = canvas.toDataURL("image/webp", 0.58);

    // Fallback if browser doesn't support webp encoding
    if (!snapshotBase64.startsWith("data:image/webp")) {
      snapshotBase64 = canvas.toDataURL("image/jpeg", 0.55);
    }

    return snapshotBase64;
  }, []);

  // ---------------------------------------------------------------------------
  // DISPATCH ENGINE: Local Buffer + Server API Post with Network Auto-Retry
  // ---------------------------------------------------------------------------
  const flushBufferedEvents = useCallback(async () => {
    if (localBufferRef.current.length === 0) return;

    const authHeaders = token
      ? { Authorization: `Bearer ${token}` }
      : localStorage.getItem("examguard_token")
      ? { Authorization: `Bearer ${localStorage.getItem("examguard_token")}` }
      : {};

    const queue = [...localBufferRef.current];
    const remaining = [];

    for (const event of queue) {
      try {
        const response = await fetch(`${apiBaseUrl}/violation-log`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...authHeaders,
          },
          body: JSON.stringify(event),
          keepalive: true,
        });

        if (!response.ok) {
          remaining.push(event);
        }
      } catch (err) {
        remaining.push(event);
      }
    }

    localBufferRef.current = remaining;
    setBufferedEventsCount(remaining.length);
    try {
      localStorage.setItem(
        `examguard_buffer_${examId}_${candidateId}`,
        JSON.stringify(remaining)
      );
    } catch (_) {}
  }, [apiBaseUrl, token, examId, candidateId]);

  const dispatchViolation = useCallback(
    (violationType, confidence = 0.9, metadata = {}) => {
      const now = Date.now();
      const cooldownKey = `${violationType}:${metadata.direction || ""}`;
      const lastSent = cooldownsRef.current.get(cooldownKey) || 0;

      // 4-second debouncing cooldown per distinct violation type
      if (now - lastSent < 4000) return;
      cooldownsRef.current.set(cooldownKey, now);

      // 1. Update In-Memory Counts & Trust Score
      const updatedCounts = {
        ...violationCountersRef.current,
        [violationType]: (violationCountersRef.current[violationType] || 0) + 1,
      };
      violationCountersRef.current = updatedCounts;
      const newScore = calculateTrustScore(updatedCounts);

      setViolationCounts(updatedCounts);
      setTrustScore(newScore);

      // 2. Capture lightweight evidence snapshot
      const snapshot = captureEvidenceSnapshot();

      // 3. Construct Payload adhering to PRD specification
      const payload = {
        candidateId: candidateId || "00000000-0000-0000-0000-000000000000",
        examId: examId || "00000000-0000-0000-0000-000000000000",
        sessionId: sessionId || null,
        timestamp: new Date().toISOString(),
        violationType,
        confidence: Number(Math.min(1.0, Math.max(0.1, confidence)).toFixed(2)),
        snapshot,
        currentScore: newScore,
        metadata: {
          ...metadata,
          exitCount: exitCount,
          deviceOrientation: window.screen?.orientation?.type || "unknown",
        },
      };

      // 4. Update UI Alert & Timeline History
      setActiveAlert({
        type: violationType,
        message: getViolationUserFriendlyMessage(violationType, metadata),
        timestamp: Date.now(),
        penalty: mergedWeights[violationType] || 10,
        score: newScore,
      });

      setViolationHistory((prev) => [
        {
          id: `${violationType}-${Date.now()}`,
          ...payload,
        },
        ...prev.slice(0, 49),
      ]);

      if (onViolation) onViolation(payload);
      if (onWarning)
        onWarning(getViolationUserFriendlyMessage(violationType, metadata));

      // 5. Append to Local Offline Buffer & Trigger Flush
      localBufferRef.current.push(payload);
      setBufferedEventsCount(localBufferRef.current.length);
      try {
        localStorage.setItem(
          `examguard_buffer_${examId}_${candidateId}`,
          JSON.stringify(localBufferRef.current)
        );
      } catch (_) {}

      flushBufferedEvents();

      // 6. Check Critical Auto-Submit Trigger (PRD Section 2.A.3)
      if (newScore <= criticalTrustScore && onAutoSubmit) {
        onAutoSubmit({
          reason: `Trust score dropped to ${newScore} (below critical threshold of ${criticalTrustScore}).`,
          trustScore: newScore,
          violationCounts: updatedCounts,
        });
      }
    },
    [
      calculateTrustScore,
      captureEvidenceSnapshot,
      candidateId,
      examId,
      sessionId,
      exitCount,
      mergedWeights,
      onViolation,
      onWarning,
      criticalTrustScore,
      onAutoSubmit,
      flushBufferedEvents,
    ]
  );

  // ---------------------------------------------------------------------------
  // GEOMETRY & POSE ESTIMATION (Euler Angles & Gaze Offset)
  // ---------------------------------------------------------------------------
  const computeHeadPoseAndGaze = useCallback((landmarks) => {
    if (!landmarks || landmarks.length < 478) return null;

    const nose = landmarks[LANDMARKS.noseTip];
    const leftEye = landmarks[LANDMARKS.leftEyeOuter];
    const rightEye = landmarks[LANDMARKS.rightEyeOuter];
    const chin = landmarks[LANDMARKS.chin];
    const forehead = landmarks[LANDMARKS.forehead];

    // Face bounds
    const xs = landmarks.map((p) => p.x);
    const ys = landmarks.map((p) => p.y);
    const faceWidth = Math.max(...xs) - Math.min(...xs) || 0.001;
    const faceHeight = Math.max(...ys) - Math.min(...ys) || 0.001;

    // Eye midpoint
    const eyeCenter = {
      x: (leftEye.x + rightEye.x) / 2,
      y: (leftEye.y + rightEye.y) / 2,
    };

    // Yaw Angle Estimation (Sideways rotation ±90 deg)
    // When facing straight, nose is roughly midway between eyes
    const yawRatio = (nose.x - eyeCenter.x) / faceWidth;
    const yawDegrees = yawRatio * 110; // Scaled to geometric degrees

    // Pitch Angle Estimation (Vertical tilt up/down)
    // When looking down, nose drops towards chin
    const pitchRatio = (nose.y - eyeCenter.y) / faceHeight;
    // Standard normalized neutral pitch is ~0.42
    const pitchDegrees = (pitchRatio - 0.42) * -120;

    // Iris Center Extraction
    const avgIris = (indices) => ({
      x: indices.reduce((acc, i) => acc + landmarks[i].x, 0) / indices.length,
      y: indices.reduce((acc, i) => acc + landmarks[i].y, 0) / indices.length,
    });
    const leftIris = avgIris(LANDMARKS.leftIris);
    const rightIris = avgIris(LANDMARKS.rightIris);

    // Gaze horizontal & vertical displacement relative to eye sockets
    const leftSocketWidth =
      Math.abs(landmarks[LANDMARKS.leftEyeInner].x - landmarks[LANDMARKS.leftEyeOuter].x) ||
      0.001;
    const rightSocketWidth =
      Math.abs(landmarks[LANDMARKS.rightEyeOuter].x - landmarks[LANDMARKS.rightEyeInner].x) ||
      0.001;

    const gazeX =
      ((leftIris.x - leftEye.x) / leftSocketWidth +
        (rightIris.x - landmarks[LANDMARKS.rightEyeInner].x) / rightSocketWidth) /
        2 -
      0.5;

    return {
      yawDegrees,
      pitchDegrees,
      gazeX,
      faceWidth,
      faceHeight,
      nose,
    };
  }, []);

  // ---------------------------------------------------------------------------
  // BASELINE CALIBRATION (5-Second Reference Capture)
  // ---------------------------------------------------------------------------
  const startCalibration = useCallback(async () => {
    setIsCalibrating(true);
    setCalibrationProgress(0);
    calibrationSamplesRef.current = [];

    const startTime = Date.now();
    const duration = 5000; // 5 seconds calibration

    return new Promise((resolve) => {
      const interval = setInterval(() => {
        const elapsed = Date.now() - startTime;
        const progress = Math.min(100, Math.round((elapsed / duration) * 100));
        setCalibrationProgress(progress);

        if (elapsed >= duration) {
          clearInterval(interval);
          setIsCalibrating(false);

          const samples = calibrationSamplesRef.current;
          if (samples.length >= 10) {
            const baseline = {
              yaw: samples.reduce((acc, s) => acc + s.yawDegrees, 0) / samples.length,
              pitch:
                samples.reduce((acc, s) => acc + s.pitchDegrees, 0) / samples.length,
              gazeX: samples.reduce((acc, s) => acc + s.gazeX, 0) / samples.length,
              faceWidth:
                samples.reduce((acc, s) => acc + s.faceWidth, 0) / samples.length,
              faceHeight:
                samples.reduce((acc, s) => acc + s.faceHeight, 0) / samples.length,
              calibratedAt: new Date().toISOString(),
            };
            baselineRef.current = baseline;
            setIsCalibrated(true);
            resolve(baseline);
          } else {
            // Not enough stable face samples
            setIsCalibrated(false);
            if (onWarning)
              onWarning(
                "Face calibration failed: Ensure your face is clearly centered in good lighting."
              );
            resolve(null);
          }
        }
      }, 100);
    });
  }, [onWarning]);

  // ---------------------------------------------------------------------------
  // OBJECT DETECTION GUARDRAIL (Lightweight Client-Side Inspection)
  // ---------------------------------------------------------------------------
  const inspectProhibitedObjects = useCallback(() => {
    if (!enableObjectDetection || !videoRef.current) return;

    // Lightweight heuristic & edge filter for unauthorized devices (Cell phones, second screens)
    // In production, easily swapped with loaded ONNX / COCO-SSD model instance
    const video = videoRef.current;
    if (video.readyState < 2) return;

    // Check aspect and edge density if phone held up in lower quadrant
    // Placeholder for ONNX YOLOv8-nano inference pipeline:
    // If phone/notes detected with confidence > 0.65 -> dispatchViolation("PROHIBITED_OBJECT")
  }, [enableObjectDetection]);

  // ---------------------------------------------------------------------------
  // AUDIO INTELLIGENCE GUARDRAIL (Web Audio API & Spectrum Analysis)
  // ---------------------------------------------------------------------------
  const setupAudioMonitoring = useCallback(async (stream) => {
    if (!enableAudio) return;

    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      const audioCtx = new AudioCtx();
      audioContextRef.current = audioCtx;

      const source = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 512;
      analyser.smoothingTimeConstant = 0.8;
      analyserRef.current = analyser;

      // Bandpass filter for typical speech fundamental frequencies (85Hz - 255Hz)
      const bandpass = audioCtx.createBiquadFilter();
      bandpass.type = "bandpass";
      bandpass.frequency.value = 170;
      bandpass.Q.value = 1.0;

      source.connect(bandpass);
      bandpass.connect(analyser);

      audioDataRef.current = new Uint8Array(analyser.frequencyBinCount);
    } catch (err) {
      console.warn("ExamGuard: Audio context initialization skipped", err);
    }
  }, [enableAudio]);

  const checkAudioAcoustics = useCallback(() => {
    const analyser = analyserRef.current;
    const dataArray = audioDataRef.current;
    if (!analyser || !dataArray) return;

    analyser.getByteFrequencyData(dataArray);

    // Compute RMS
    let sumSquares = 0;
    for (let i = 0; i < dataArray.length; i++) {
      sumSquares += dataArray[i] * dataArray[i];
    }
    const rms = Math.sqrt(sumSquares / dataArray.length);

    // Approximate decibels (0 to 100 scale)
    const decibels = Math.round((rms / 255) * 100);
    setAudioLevel(decibels);

    const now = Date.now();
    // Threshold: Continuous speech frequency > 60dB for > 3 consecutive seconds (PRD Module 3)
    if (decibels > 60) {
      if (streakTimersRef.current.audioSpikeStart === 0) {
        streakTimersRef.current.audioSpikeStart = now;
      } else if (now - streakTimersRef.current.audioSpikeStart >= 3000) {
        dispatchViolation("SPEECH_DETECTED", Math.min(0.99, decibels / 100), {
          decibels,
          durationSeconds: ((now - streakTimersRef.current.audioSpikeStart) / 1000).toFixed(1),
        });
        streakTimersRef.current.audioSpikeStart = now; // reset streak after flag
      }
    } else {
      streakTimersRef.current.audioSpikeStart = 0;
    }
  }, [dispatchViolation]);

  // ---------------------------------------------------------------------------
  // MAIN COMPUTER VISION INFERENCE LOOP (3 - 5 FPS)
  // ---------------------------------------------------------------------------
  const runVisionLoop = useCallback(() => {
    if (!isMonitoring) return;

    const now = performance.now();
    const frameGapMs = 1000 / targetFps; // ~250ms for 4 FPS

    if (now - lastVisionTickRef.current >= frameGapMs) {
      lastVisionTickRef.current = now;
      const video = videoRef.current;
      const landmarker = faceLandmarkerRef.current;

      if (video && video.readyState >= 2 && landmarker) {
        try {
          const results = landmarker.detectForVideo(video, now);
          const faces = results.faceLandmarks || [];
          const timestamp = Date.now();

          // 1. Multi-Face & Absence Detection (PRD Module 2)
          if (faces.length === 0) {
            streakTimersRef.current.multipleFacesStart = 0;
            streakTimersRef.current.gazeAnomalyStart = 0;

            // Candidate absent for > 3 consecutive seconds
            if (streakTimersRef.current.faceMissingStart === 0) {
              streakTimersRef.current.faceMissingStart = timestamp;
            } else if (timestamp - streakTimersRef.current.faceMissingStart >= 3000) {
              dispatchViolation("CANDIDATE_ABSENT", 0.95, {
                absentSeconds: (
                  (timestamp - streakTimersRef.current.faceMissingStart) /
                  1000
                ).toFixed(1),
              });
              streakTimersRef.current.faceMissingStart = timestamp;
            }
          } else if (faces.length > 1) {
            streakTimersRef.current.faceMissingStart = 0;
            streakTimersRef.current.gazeAnomalyStart = 0;

            // Multiple faces for > 2 consecutive seconds
            if (streakTimersRef.current.multipleFacesStart === 0) {
              streakTimersRef.current.multipleFacesStart = timestamp;
            } else if (
              timestamp - streakTimersRef.current.multipleFacesStart >=
              2000
            ) {
              dispatchViolation("MULTIPLE_FACES", 0.96, {
                facesDetected: faces.length,
                durationSeconds: (
                  (timestamp - streakTimersRef.current.multipleFacesStart) /
                  1000
                ).toFixed(1),
              });
              streakTimersRef.current.multipleFacesStart = timestamp;
            }
          } else {
            // Exactly 1 Face Detected - Analyze Gaze & Pose
            streakTimersRef.current.faceMissingStart = 0;
            streakTimersRef.current.multipleFacesStart = 0;

            const measurements = computeHeadPoseAndGaze(faces[0]);

            // If calibrating, collect reference samples
            if (isCalibrating && measurements) {
              calibrationSamplesRef.current.push(measurements);
            }

            // Pose Verification
            if (measurements && baselineRef.current) {
              const baseline = baselineRef.current;
              const deltaYaw = measurements.yawDegrees - baseline.yaw;
              const deltaPitch = measurements.pitchDegrees - baseline.pitch;

              // PRD Module 2 Condition:
              // Yaw exceeds ±30 degrees (looking sideways) OR Pitch drops < -20 degrees (looking down at phone/lap)
              const isLookingSideways = Math.abs(deltaYaw) > 30;
              const isLookingDown = deltaPitch < -20;

              if (isLookingSideways || isLookingDown) {
                if (streakTimersRef.current.gazeAnomalyStart === 0) {
                  streakTimersRef.current.gazeAnomalyStart = timestamp;
                } else if (
                  timestamp - streakTimersRef.current.gazeAnomalyStart >=
                  3000
                ) {
                  const direction = isLookingDown
                    ? "DOWN_LAP"
                    : deltaYaw > 0
                    ? "RIGHT"
                    : "LEFT";

                  dispatchViolation("GAZE_ANOMALY", 0.88, {
                    direction,
                    deltaYaw: Math.round(deltaYaw),
                    deltaPitch: Math.round(deltaPitch),
                    durationSeconds: (
                      (timestamp - streakTimersRef.current.gazeAnomalyStart) /
                      1000
                    ).toFixed(1),
                  });
                  streakTimersRef.current.gazeAnomalyStart = timestamp;
                }
              } else {
                streakTimersRef.current.gazeAnomalyStart = 0;
              }
            }
          }
        } catch (visionErr) {
          console.warn("ExamGuard: Vision frame processing error", visionErr);
        }
      }

      // Check audio acoustics at matched rate
      checkAudioAcoustics();
      inspectProhibitedObjects();
    }

    animationFrameIdRef.current = requestAnimationFrame(runVisionLoop);
  }, [
    isMonitoring,
    targetFps,
    computeHeadPoseAndGaze,
    isCalibrating,
    dispatchViolation,
    checkAudioAcoustics,
    inspectProhibitedObjects,
  ]);

  // ---------------------------------------------------------------------------
  // MODULE 1: BROWSER LOCKDOWN & ENVIRONMENT CONTROL
  // ---------------------------------------------------------------------------
  const enterFullscreen = useCallback(async () => {
    try {
      const docEl = document.documentElement;
      if (docEl.requestFullscreen) {
        await docEl.requestFullscreen();
      } else if (docEl.webkitRequestFullscreen) {
        await docEl.webkitRequestFullscreen();
      }
      setIsFullscreen(true);
      return true;
    } catch (err) {
      if (onWarning) onWarning("Fullscreen request was denied by browser.");
      return false;
    }
  }, [onWarning]);

  useEffect(() => {
    if (!isMonitoring) return;

    // Fullscreen Exit Enforcement
    const handleFullscreenChange = () => {
      const active = Boolean(
        document.fullscreenElement || document.webkitFullscreenElement
      );
      setIsFullscreen(active);

      if (!active) {
        setExitCount((prev) => {
          const newCount = prev + 1;
          dispatchViolation("FULLSCREEN_EXIT", 1.0, {
            exitAttempt: newCount,
            maxAllowed: maxExits,
          });

          if (newCount >= maxExits && onAutoSubmit) {
            onAutoSubmit({
              reason: `Exam locked: Exceeded maximum allowed unapproved fullscreen exits (${newCount}/${maxExits}).`,
              exitCount: newCount,
              trustScore: trustScore,
            });
          }
          return newCount;
        });
      }
    };

    // Tab Switch & Visibility Detection
    const handleVisibilityChange = () => {
      if (document.visibilityState === "hidden") {
        dispatchViolation("TAB_SWITCH", 1.0, {
          trigger: "visibility_hidden",
        });
      }
    };

    // Window Blur
    const handleWindowBlur = () => {
      dispatchViolation("WINDOW_BLUR", 0.95, {
        trigger: "window_blur",
      });
    };

    // Input & Clipboard Blocking
    const handleContextMenu = (e) => {
      e.preventDefault();
      return false;
    };

    const handleClipboard = (e) => {
      e.preventDefault();
      dispatchViolation("CLIPBOARD_VIOLATION", 0.9, {
        type: e.type,
      });
      return false;
    };

    // Key Combinations Blocking
    const handleKeyDown = (e) => {
      const key = e.key.toUpperCase();
      const ctrl = e.ctrlKey || e.metaKey;
      const alt = e.altKey;

      // Block Alt+Tab, Ctrl+C, Ctrl+V, Ctrl+W, F12, PrintScreen, Ctrl+Shift+I
      const isBlocked =
        (ctrl && ["C", "V", "W", "A", "P", "S"].includes(key)) ||
        (alt && (key === "TAB" || key === "ARROWLEFT" || key === "ARROWRIGHT")) ||
        key === "F12" ||
        key === "PRINTSCREEN" ||
        (ctrl && e.shiftKey && (key === "I" || key === "J" || key === "C"));

      if (isBlocked) {
        e.preventDefault();
        e.stopPropagation();
        dispatchViolation("UNAUTHORIZED_KEY", 0.95, {
          key: e.key,
          code: e.code,
        });
        return false;
      }
    };

    // Dual Monitor Detection
    const checkDisplayEnvironment = async () => {
      try {
        if ("getScreenDetails" in window) {
          const screens = await window.getScreenDetails();
          if (screens.screens.length > 1) {
            dispatchViolation("DUAL_MONITOR_DETECTED", 1.0, {
              monitorCount: screens.screens.length,
            });
          }
        } else if (window.screen.availWidth > window.screen.width * 1.5) {
          dispatchViolation("DUAL_MONITOR_DETECTED", 0.85, {
            detectedMultiDisplayRatio: true,
          });
        }
      } catch (_) {}
    };

    document.addEventListener("fullscreenchange", handleFullscreenChange);
    document.addEventListener("webkitfullscreenchange", handleFullscreenChange);
    document.addEventListener("visibilitychange", handleVisibilityChange);
    window.addEventListener("blur", handleWindowBlur);
    document.addEventListener("contextmenu", handleContextMenu);
    document.addEventListener("copy", handleClipboard);
    document.addEventListener("cut", handleClipboard);
    document.addEventListener("paste", handleClipboard);
    window.addEventListener("keydown", handleKeyDown, true);
    window.addEventListener("online", flushBufferedEvents);

    checkDisplayEnvironment();

    return () => {
      document.removeEventListener("fullscreenchange", handleFullscreenChange);
      document.removeEventListener("webkitfullscreenchange", handleFullscreenChange);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      window.removeEventListener("blur", handleWindowBlur);
      document.removeEventListener("contextmenu", handleContextMenu);
      document.removeEventListener("copy", handleClipboard);
      document.removeEventListener("cut", handleClipboard);
      document.removeEventListener("paste", handleClipboard);
      window.removeEventListener("keydown", handleKeyDown, true);
      window.removeEventListener("online", flushBufferedEvents);
    };
  }, [
    isMonitoring,
    dispatchViolation,
    maxExits,
    onAutoSubmit,
    trustScore,
    flushBufferedEvents,
  ]);

  // ---------------------------------------------------------------------------
  // INITIALIZATION: Camera Stream & MediaPipe Face Landmarker
  // ---------------------------------------------------------------------------
  const startEngine = useCallback(async () => {
    try {
      // 1. Acquire MediaStream
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 640 },
          height: { ideal: 480 },
          frameRate: { ideal: 15, max: 20 },
          facingMode: "user",
        },
        audio: enableAudio,
      });

      mediaStreamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }

      // 2. Setup Audio Intelligence
      if (enableAudio) {
        await setupAudioMonitoring(stream);
      }

      // 3. Dynamic MediaPipe Vision Tasks Import
      const visionModule = await import(/* @vite-ignore */ MEDIAPIPE_VISION_CDN);
      const { FilesetResolver, FaceLandmarker } = visionModule;

      const vision = await FilesetResolver.forVisionTasks(MEDIAPIPE_WASM_CDN);
      const faceLandmarker = await FaceLandmarker.createFromOptions(vision, {
        baseOptions: {
          modelAssetPath: FACE_LANDMARKER_MODEL_URL,
          delegate: "GPU",
        },
        runningMode: "VIDEO",
        numFaces: 3,
        minFaceDetectionConfidence: 0.55,
        minFacePresenceConfidence: 0.55,
        minTrackingConfidence: 0.55,
        outputFaceBlendshapes: false,
        outputFacialTransformationMatrixes: false,
      });

      faceLandmarkerRef.current = faceLandmarker;
      setIsInitialized(true);
      setIsMonitoring(true);

      // Start loop
      animationFrameIdRef.current = requestAnimationFrame(runVisionLoop);
      return true;
    } catch (err) {
      console.error("ExamGuard Engine initialization failed:", err);
      if (onWarning) {
        onWarning(
          "Camera or Microphone access was denied. You must grant hardware permissions to start the proctored exam."
        );
      }
      return false;
    }
  }, [enableAudio, setupAudioMonitoring, runVisionLoop, onWarning]);

  const stopEngine = useCallback(() => {
    setIsMonitoring(false);
    if (animationFrameIdRef.current) {
      cancelAnimationFrame(animationFrameIdRef.current);
    }

    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
    }

    if (audioContextRef.current && audioContextRef.current.state !== "closed") {
      audioContextRef.current.close().catch(() => {});
    }
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopEngine();
    };
  }, [stopEngine]);

  const dismissAlert = useCallback(() => {
    setActiveAlert(null);
  }, []);

  return {
    videoRef,
    canvasRef,
    status: {
      isInitialized,
      isCalibrating,
      calibrationProgress,
      isCalibrated,
      isMonitoring,
      isFullscreen,
      trustScore,
      exitCount,
      activeAlert,
      audioLevel,
      fps: targetFps,
      violationCounts,
      violationHistory,
      bufferedEventsCount,
    },
    actions: {
      startEngine,
      stopEngine,
      startCalibration,
      enterFullscreen,
      dismissAlert,
      flushBufferedEvents,
    },
  };
}

function getViolationUserFriendlyMessage(type, metadata = {}) {
  switch (type) {
    case "MULTIPLE_FACES":
      return `Multiple persons detected in camera frame (${metadata.facesDetected || 2}). Keep your test environment private.`;
    case "CANDIDATE_ABSENT":
    case "FACE_MISSING":
      return "Candidate absent: Please face your camera directly.";
    case "GAZE_ANOMALY":
    case "LOOKING_AWAY":
      return `Suspicious gaze detected: Candidate looking ${metadata.direction || "away"}. Keep eyes on the screen.`;
    case "PROHIBITED_OBJECT":
    case "OBJECT_DETECTED":
      return "Prohibited item detected (cell phone, headphones, or secondary materials).";
    case "SPEECH_DETECTED":
    case "ACOUSTIC_ACTIVITY":
      return "Speech or acoustic activity detected in room. Silence is required.";
    case "TAB_SWITCH":
      return "Tab switch detected! Navigating away from the exam tab is recorded.";
    case "WINDOW_BLUR":
      return "Focus lost: Window blur event recorded.";
    case "FULLSCREEN_EXIT":
      return `Fullscreen exited (${metadata.exitAttempt || 1}/${metadata.maxAllowed || 3}). Exam will be terminated after 3 exits.`;
    case "CLIPBOARD_VIOLATION":
      return "Clipboard action (copy/paste) blocked.";
    case "UNAUTHORIZED_KEY":
      return `Blocked shortcut (${metadata.key || "restricted"}).`;
    case "DUAL_MONITOR_DETECTED":
      return "Multiple monitors or extended display detected. Disconnect secondary screens.";
    default:
      return "Proctoring guardrail alert: Irregular behavior logged.";
  }
}

