import {
  FaceLandmarker,
  FilesetResolver,
} from "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.22/vision_bundle.mjs";

const PROCTOR_MODEL_URL =
  "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task";
const PROCTOR_WASM_URL =
  "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.22/wasm";

const AI_CHEAT_EVENTS = {
  faceMissing: "FACE_MISSING",
  lookingAway: "LOOKING_AWAY",
  multipleFaces: "MULTIPLE_FACES",
};

const proctorState = {
  faceLandmarker: null,
  running: false,
  lastFrameAt: 0,
  neutral: null,
  neutralSamples: [],
  violationKey: "",
  violationFrames: 0,
  cooldowns: new Map(),
};

const LANDMARKS = {
  noseTip: 1,
  leftEyeOuter: 33,
  leftEyeInner: 133,
  rightEyeInner: 362,
  rightEyeOuter: 263,
  leftEyeTop: 159,
  leftEyeBottom: 145,
  rightEyeTop: 386,
  rightEyeBottom: 374,
  leftIris: [468, 469, 470, 471, 472],
  rightIris: [473, 474, 475, 476, 477],
};

function average(points) {
  return {
    x: points.reduce((sum, point) => sum + point.x, 0) / points.length,
    y: points.reduce((sum, point) => sum + point.y, 0) / points.length,
  };
}

function faceBounds(landmarks) {
  const xs = landmarks.map((point) => point.x);
  const ys = landmarks.map((point) => point.y);
  return {
    width: Math.max(...xs) - Math.min(...xs),
    height: Math.max(...ys) - Math.min(...ys),
  };
}

function irisCenter(landmarks, indices) {
  if (landmarks.length <= Math.max(...indices)) return null;
  return average(indices.map((index) => landmarks[index]));
}

function faceMeasurements(landmarks) {
  const nose = landmarks[LANDMARKS.noseTip];
  const bounds = faceBounds(landmarks);
  const eyeCenter = average([
    landmarks[LANDMARKS.leftEyeOuter],
    landmarks[LANDMARKS.rightEyeOuter],
  ]);
  const yaw = (nose.x - eyeCenter.x) / bounds.width;
  const pitch = (nose.y - eyeCenter.y) / bounds.height;
  const leftIris = irisCenter(landmarks, LANDMARKS.leftIris);
  const rightIris = irisCenter(landmarks, LANDMARKS.rightIris);

  if (!leftIris || !rightIris) {
    return { yaw, pitch, gazeX: 0, gazeY: 0, hasIris: false };
  }

  const leftEyeCenter = average([
    landmarks[LANDMARKS.leftEyeOuter],
    landmarks[LANDMARKS.leftEyeInner],
  ]);
  const rightEyeCenter = average([
    landmarks[LANDMARKS.rightEyeInner],
    landmarks[LANDMARKS.rightEyeOuter],
  ]);
  const leftEyeWidth = Math.abs(
    landmarks[LANDMARKS.leftEyeInner].x - landmarks[LANDMARKS.leftEyeOuter].x
  );
  const rightEyeWidth = Math.abs(
    landmarks[LANDMARKS.rightEyeOuter].x - landmarks[LANDMARKS.rightEyeInner].x
  );
  const leftEyeHeight = Math.abs(
    landmarks[LANDMARKS.leftEyeTop].y - landmarks[LANDMARKS.leftEyeBottom].y
  );
  const rightEyeHeight = Math.abs(
    landmarks[LANDMARKS.rightEyeTop].y - landmarks[LANDMARKS.rightEyeBottom].y
  );

  return {
    yaw,
    pitch,
    gazeX:
      ((leftIris.x - leftEyeCenter.x) / leftEyeWidth +
        (rightIris.x - rightEyeCenter.x) / rightEyeWidth) /
      2,
    gazeY:
      ((leftIris.y - leftEyeCenter.y) / leftEyeHeight +
        (rightIris.y - rightEyeCenter.y) / rightEyeHeight) /
      2,
    hasIris: true,
  };
}

function calibrateNeutral(measurements) {
  if (proctorState.neutral) return true;

  proctorState.neutralSamples.push(measurements);
  if (proctorState.neutralSamples.length < 18) return false;

  const samples = proctorState.neutralSamples;
  proctorState.neutral = {
    yaw: samples.reduce((sum, item) => sum + item.yaw, 0) / samples.length,
    pitch: samples.reduce((sum, item) => sum + item.pitch, 0) / samples.length,
    gazeX: samples.reduce((sum, item) => sum + item.gazeX, 0) / samples.length,
    gazeY: samples.reduce((sum, item) => sum + item.gazeY, 0) / samples.length,
  };
  return true;
}

function lookingAwayDirection(landmarks) {
  const measurements = faceMeasurements(landmarks);
  if (!calibrateNeutral(measurements)) return null;

  const neutral = proctorState.neutral;
  const dx = measurements.hasIris
    ? measurements.gazeX - neutral.gazeX
    : measurements.yaw - neutral.yaw;
  const dy = measurements.hasIris
    ? measurements.gazeY - neutral.gazeY
    : measurements.pitch - neutral.pitch;
  const horizontalThreshold = measurements.hasIris ? 0.14 : 0.08;
  const verticalThreshold = measurements.hasIris ? 0.22 : 0.07;

  if (Math.abs(dx) > horizontalThreshold) {
    return {
      direction: dx > 0 ? "RIGHT" : "LEFT",
      confidence: Math.min(0.99, Math.abs(dx) / horizontalThreshold / 2),
    };
  }
  if (Math.abs(dy) > verticalThreshold) {
    return {
      direction: dy > 0 ? "DOWN" : "UP",
      confidence: Math.min(0.99, Math.abs(dy) / verticalThreshold / 2),
    };
  }
  return null;
}

function markViolation(eventType, details = {}) {
  const key = `${eventType}:${details.direction || ""}`;
  if (proctorState.violationKey === key) {
    proctorState.violationFrames += 1;
  } else {
    proctorState.violationKey = key;
    proctorState.violationFrames = 1;
  }

  if (proctorState.violationFrames < 4) return;

  const now = Date.now();
  const lastSentAt = proctorState.cooldowns.get(key) || 0;
  if (now - lastSentAt < 5000) return;

  proctorState.cooldowns.set(key, now);
  window.ExamGuardTracking?.sendEvent?.(
    eventType,
    "Camera AI detected suspicious exam behavior.",
    {
      detected_at: new Date().toISOString(),
      detector: "MEDIAPIPE_FACE_LANDMARKER",
      ...details,
    },
    { keepalive: true }
  );
}

async function loadFaceLandmarker() {
  if (proctorState.faceLandmarker) return proctorState.faceLandmarker;

  const vision = await FilesetResolver.forVisionTasks(PROCTOR_WASM_URL);
  proctorState.faceLandmarker = await FaceLandmarker.createFromOptions(vision, {
    baseOptions: {
      modelAssetPath: PROCTOR_MODEL_URL,
      delegate: "GPU",
    },
    runningMode: "VIDEO",
    numFaces: 2,
    minFaceDetectionConfidence: 0.6,
    minFacePresenceConfidence: 0.6,
    minTrackingConfidence: 0.6,
    outputFaceBlendshapes: true,
    outputFacialTransformationMatrixes: true,
  });
  return proctorState.faceLandmarker;
}

function proctorLoop() {
  if (!proctorState.running) return;

  const video = document.querySelector("#cameraPreview");
  const landmarker = proctorState.faceLandmarker;
  const now = performance.now();
  const minFrameGapMs = 1000 / 12;

  if (
    video?.readyState >= 2 &&
    landmarker &&
    now - proctorState.lastFrameAt >= minFrameGapMs
  ) {
    proctorState.lastFrameAt = now;
    const result = landmarker.detectForVideo(video, now);
    const faces = result.faceLandmarks || [];

    if (!faces.length) {
      markViolation(AI_CHEAT_EVENTS.faceMissing, { confidence: 0.95 });
    } else if (faces.length > 1) {
      markViolation(AI_CHEAT_EVENTS.multipleFaces, {
        face_count: faces.length,
        confidence: 0.95,
      });
    } else {
      const away = lookingAwayDirection(faces[0]);
      if (away) {
        markViolation(AI_CHEAT_EVENTS.lookingAway, away);
      } else {
        proctorState.violationKey = "";
        proctorState.violationFrames = 0;
      }
    }
  }

  requestAnimationFrame(proctorLoop);
}

async function startAiProctoring() {
  if (proctorState.running || window.ExamGuardTracking?.shouldBlockMobileExam?.()) {
    return;
  }

  const video = document.querySelector("#cameraPreview");
  if (!video) return;

  await loadFaceLandmarker();
  proctorState.running = true;
  proctorLoop();
}

document.addEventListener("examguard:precheck-complete", startAiProctoring);
document.addEventListener("examguard:student-ready", () => {
  window.setTimeout(startAiProctoring, 1500);
});

window.ExamGuardAIProctor = {
  start: startAiProctoring,
  isRunning: () => proctorState.running,
};
