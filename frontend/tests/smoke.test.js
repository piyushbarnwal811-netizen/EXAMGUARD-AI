import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

function read(relativePath) {
  return readFileSync(join(root, relativePath), "utf8");
}

test("exam page wires webcam controls and scripts", () => {
  const html = read("src/pages/exam.html");

  assert.match(html, /data-camera-panel/);
  assert.match(html, /id="cameraPreview"/);
  assert.match(html, /data-camera-start/);
  assert.match(html, /data-camera-stop/);
  assert.match(html, /src="\.\.\/js\/camera\.js"/);
  assert.match(html, /src="\.\.\/js\/tracking\.js"/);
  assert.match(html, /src="\.\.\/js\/proctor_ai\.js"/);
  assert.match(html, /src="\.\.\/js\/precheck\.js"/);
  assert.match(html, /data-precheck-panel/);
  assert.match(html, /data-location-status/);
});

test("admin page exposes coding question management", () => {
  const html = read("src/pages/admin.html");
  const main = read("src/js/main.js");

  assert.match(html, /id="aiQuestionForm"/);
  assert.match(html, /id="aiTopic"/);
  assert.match(html, /id="aiDifficulty"/);
  assert.match(html, /data-ai-question-results/);
  assert.match(html, /id="codingProblemForm"/);
  assert.match(html, /data-test-cases/);
  assert.match(html, /id="starterPython"/);
  assert.match(main, /\/questions\/generate/);
  assert.match(main, /generatedQuestionToProblem/);
  assert.match(main, /\/contest\/problems-admin/);
  assert.match(main, /Exactly 2 test cases must be marked visible/);
});

test("camera script requests webcam and logs lifecycle events", () => {
  const camera = read("src/js/camera.js");

  assert.match(camera, /navigator\.mediaDevices\.getUserMedia/);
  assert.match(camera, /CAMERA_PERMISSION_REQUESTED/);
  assert.match(camera, /CAMERA_STARTED/);
  assert.match(camera, /CAMERA_STOPPED/);
  assert.match(camera, /CAMERA_PERMISSION_DENIED/);
  assert.match(camera, /ExamGuardTracking\.sendEvent/);
});

test("tracking script records mobile device usage time", () => {
  const tracking = read("src/js/tracking.js");
  const main = read("src/js/main.js");

  assert.match(tracking, /detectMobileDevice/);
  assert.match(tracking, /reportMobileDeviceUse/);
  assert.match(tracking, /MOBILE_DEVICE_DETECTED/);
  assert.match(tracking, /MOBILE_DEVICE_BLOCKED/);
  assert.match(tracking, /detected_at/);
  assert.match(tracking, /client_timezone/);
  assert.match(main, /blockMobileExam/);
});

test("camera AI proctor sends suspicious behavior events without frames", () => {
  const ai = read("src/js/proctor_ai.js");

  assert.match(ai, /FaceLandmarker/);
  assert.match(ai, /detectForVideo/);
  assert.match(ai, /FACE_MISSING/);
  assert.match(ai, /LOOKING_AWAY/);
  assert.match(ai, /MULTIPLE_FACES/);
  assert.match(ai, /ExamGuardTracking\?\.sendEvent/);
});

test("lockdown script tracks fullscreen and focus violations", () => {
  const lockdown = read("src/js/lockdown.js");

  assert.match(lockdown, /visibilitychange/);
  assert.match(lockdown, /window\.addEventListener\("blur"/);
  assert.match(lockdown, /window\.addEventListener\("pagehide"/);
  assert.match(lockdown, /examActive/);
  assert.match(lockdown, /escapeLocked/);
  assert.match(lockdown, /setExamActive/);
  assert.match(lockdown, /FULLSCREEN_EXIT/);
  assert.match(lockdown, /FULLSCREEN_RESUME_FAILED/);
  assert.match(lockdown, /FOCUS_LOST/);
  assert.match(lockdown, /BLOCKED_KEY/);
  assert.match(lockdown, /ExamGuardLockdown/);
});

test("coding contest shows final marks after the exam ends", () => {
  const coding = read("src/js/coding.js");
  const css = read("src/css/style.css");

  assert.match(coding, /final_result/);
  assert.match(coding, /Final Marks/);
  assert.match(coding, /latestFinalResult/);
  assert.match(coding, /setExamActive/);
  assert.match(css, /final-score-card/);
  assert.match(css, /score-value/);
});

test("precheck gates the contest on system camera location and fullscreen", () => {
  const precheck = read("src/js/precheck.js");
  const coding = read("src/js/coding.js");

  assert.match(precheck, /checkSystemCompatibility/);
  assert.match(precheck, /ExamGuardCamera.*start/);
  assert.match(precheck, /sendLocation/);
  assert.match(precheck, /ExamGuardLockdown.*start/);
  assert.match(coding, /examguard:precheck-complete/);
  assert.match(coding, /showPrecheckRequired/);
});
