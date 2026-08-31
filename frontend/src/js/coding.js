const CODING_API_BASE = window.EXAMGUARD_API_BASE || "/api";
const MONACO_CDN_VS = "https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.49.0/min/vs";

const codingState = {
  editor: null,
  monacoReady: null,
  problem: null,
  problems: [],
  submittedProblemIds: new Set(),
  problemResults: new Map(),
  currentLanguage: "python",
  serverOffsetMs: 0,
  countdownTimer: null,
  statusTimer: null,
  submitInFlight: false,
  editorLocked: false,
  autoSubmitted: false,
  examSubmitted: false,
  pendingContestData: null,
  draftSaveTimer: null,
  serverDraftTimer: null,
  serverDraftInterval: null,
  lastServerDraftSignature: "",
  draftSaveInFlight: false,
  emergencySubmitSent: false,
  latestFinalResult: null,
};

const codingQs = (selector) => document.querySelector(selector);
const htmlEscape =
  typeof escapeHtml === "function"
    ? escapeHtml
    : (value) =>
        String(value).replace(/[&<>"']/g, (char) => {
          const entities = {
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#039;",
          };
          return entities[char];
        });

function setContestStatus(message, type = "") {
  const status = codingQs("[data-contest-status]");
  if (!status) return;
  status.className = `muted ${type}`.trim();
  status.textContent = message;
}

function setVisible(element, visible) {
  if (element) element.hidden = !visible;
}

function setExamActiveLock(active) {
  window.ExamGuardLockdown?.setExamActive?.(active);
}

function formatHms(totalSeconds) {
  const seconds = Math.max(0, Number(totalSeconds || 0));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  return [hours, minutes, secs].map((value) => String(value).padStart(2, "0")).join(":");
}

function syncServerClock(serverTime) {
  const serverMs = new Date(serverTime).getTime();
  if (!Number.isNaN(serverMs)) {
    codingState.serverOffsetMs = serverMs - Date.now();
  }
}

function serverNowMs() {
  return Date.now() + codingState.serverOffsetMs;
}

function secondsUntil(isoTime) {
  const targetMs = new Date(isoTime).getTime();
  if (Number.isNaN(targetMs)) return 0;
  return Math.max(0, Math.ceil((targetMs - serverNowMs()) / 1000));
}

async function codingGet(path) {
  const response = await fetch(`${CODING_API_BASE}${path}`, {
    headers: authHeaders(),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(errorMessageFromPayload(error));
  }
  return response.json();
}

async function codingPost(path, payload) {
  const response = await fetch(`${CODING_API_BASE}${path}`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(errorMessageFromPayload(error));
  }
  return response.json();
}

function showAccessRequired() {
  setExamActiveLock(false);
  setVisible(codingQs("[data-workspace]"), false);
  setVisible(codingQs("[data-lock-screen]"), true);
  codingQs("[data-lock-state]").textContent = "Access Required";
  codingQs("[data-lock-title]").textContent = "Invitation Required";
  codingQs("[data-lock-countdown]").textContent = "--:--:--";
  codingQs("[data-lock-copy]").textContent = "Open a valid exam invitation or login again.";
  renderFinalScore(null);
  setContestStatus("Student access required.", "warning");
}

function showLockedState(data) {
  if (data.status !== "ACTIVE") {
    setExamActiveLock(false);
  }
  setVisible(codingQs("[data-workspace]"), false);
  setVisible(codingQs("[data-lock-screen]"), true);
  codingQs("[data-lock-state]").textContent = data.status;
  codingQs("[data-lock-title]").textContent =
    data.status === "ENDED" ? "Contest Ended" : "Contest Locked";
  const finalResult = data.status === "ENDED"
    ? (data.final_results?.length ? data.final_results : data.final_result || codingState.latestFinalResult)
    : null;
  codingQs("[data-lock-copy]").textContent =
    finalResult
      ? "Your final marks are ready."
      : data.message ||
    (data.status === "ENDED"
      ? "The submission window is closed."
      : "Waiting for the scheduled start time.");
  renderFinalScore(finalResult);
  setContestStatus(
    finalResult
      ? finalScoreText(finalResult)
      : data.status === "ENDED"
        ? "Contest ended."
        : "Contest locked by server time.",
    finalResult ? "success" : data.status === "ENDED" ? "warning" : ""
  );

  const target = data.status === "LOCKED" ? data.start_time : null;
  startCountdown(target, data.status);

  if (data.status === "ENDED") {
    window.ExamGuardLockdown?.markSubmitted?.();
  } else if (precheckComplete()) {
    ensureContestFullscreen(`contest_${String(data.status).toLowerCase()}`).catch(
      () => undefined
    );
  }
}

function precheckComplete() {
  return !window.ExamGuardExamGate?.requiresPrecheck?.() || window.ExamGuardExamGate.isComplete();
}

async function ensureContestFullscreen(trigger = "contest_gate") {
  if (!window.ExamGuardLockdown?.start) return false;
  if (window.ExamGuardLockdown.hasStarted?.() && document.fullscreenElement) {
    return true;
  }
  return window.ExamGuardLockdown.start({ requestedBy: trigger });
}

function showPrecheckRequired() {
  setVisible(codingQs("[data-workspace]"), false);
  setVisible(codingQs("[data-lock-screen]"), false);
  renderFinalScore(null);
  window.ExamGuardExamGate?.show?.();
  setContestStatus("Complete system, camera, and location checks to start.", "warning");
}

function ensureFinalScorePanel() {
  let panel = codingQs("[data-final-score]");
  if (panel) return panel;

  const lockScreen = codingQs("[data-lock-screen]");
  const lockCopy = codingQs("[data-lock-copy]");
  if (!lockScreen) return null;

  panel = document.createElement("div");
  panel.className = "final-score-card";
  panel.dataset.finalScore = "true";
  panel.hidden = true;
  lockCopy?.insertAdjacentElement("afterend", panel);
  return panel;
}

function finalScoreSummary(result) {
  if (Array.isArray(result)) {
    const results = result.filter(Boolean);
    if (!results.length) return null;
    const score = results.reduce((total, item) => total + Number(item.score || 0), 0);
    const maxScore = results.length * 100;
    const passed = results.reduce((total, item) => total + Number(item.passed_cases || 0), 0);
    const totalCases = results.reduce((total, item) => total + Number(item.total_cases || 0), 0);
    return { score, maxScore, passed, totalCases, questions: results.length };
  }

  if (!result) return null;
  return {
    score: Number(result.score || 0),
    maxScore: 100,
    passed: Number(result.passed_cases || 0),
    totalCases: Number(result.total_cases || 0),
    questions: 1,
  };
}

function finalScoreText(result) {
  const summary = finalScoreSummary(result);
  if (!summary) return "";
  return `Final marks: ${summary.score.toFixed(2)} / ${summary.maxScore}.`;
}

function renderFinalScore(result) {
  const panel = ensureFinalScorePanel();
  if (!panel) return;

  const summary = finalScoreSummary(result);
  if (!summary) {
    panel.hidden = true;
    panel.innerHTML = "";
    return;
  }

  panel.hidden = false;
  panel.innerHTML = `
    <p class="eyebrow">Final Marks</p>
    <div class="score-value">${summary.score.toFixed(2)} / ${summary.maxScore}</div>
    <p class="muted">${summary.passed} of ${summary.totalCases} test cases passed across ${summary.questions} question(s).</p>
  `;
}

function showFinalResultScreen(result) {
  codingState.latestFinalResult = result;
  setExamActiveLock(false);
  setEditorLocked(true);
  setVisible(codingQs("[data-workspace]"), false);
  setVisible(codingQs("[data-lock-screen]"), true);
  codingQs("[data-lock-state]").textContent = "ENDED";
  codingQs("[data-lock-title]").textContent = "Contest Ended";
  codingQs("[data-lock-countdown]").textContent = "00:00:00";
  codingQs("[data-lock-copy]").textContent = "Your final marks are ready.";
  renderFinalScore(result);
  setContestStatus(finalScoreText(result), "success");
}

function renderProblem(problem) {
  codingQs("[data-problem-title]").textContent = problem.title;
  codingQs("[data-problem-body]").innerHTML = `
    <p>${htmlEscape(problem.statement)}</p>
    <h3>Input</h3>
    <p>${htmlEscape(problem.input_format)}</p>
    <h3>Output</h3>
    <p>${htmlEscape(problem.output_format)}</p>
    <h3>Constraints</h3>
    <pre>${htmlEscape(problem.constraints)}</pre>
  `;

  const samples = problem.visible_samples || [];
  codingQs("[data-visible-samples]").innerHTML = samples
    .map(
      (sample) => `
        <article class="sample-card">
          <div class="case-head">
            <strong>Sample ${Number(sample.case_number)}</strong>
          </div>
          <label>Input</label>
          <pre>${htmlEscape(sample.input_data)}</pre>
          <label>Expected Output</label>
          <pre>${htmlEscape(sample.expected_output)}</pre>
        </article>
      `
    )
    .join("");
}

function isProblemSubmitted(problemId) {
  return codingState.submittedProblemIds.has(Number(problemId));
}

function allProblemsSubmitted() {
  return Boolean(
    codingState.problems.length &&
      codingState.problems.every((problem) => isProblemSubmitted(problem.id))
  );
}

function renderProblemTabs() {
  const holder = codingQs("[data-problem-tabs]");
  if (!holder) return;

  if (codingState.problems.length <= 1) {
    holder.innerHTML = "";
    return;
  }

  holder.innerHTML = codingState.problems
    .map((problem, index) => {
      const isActive = codingState.problem?.id === problem.id;
      const submitted = isProblemSubmitted(problem.id);
      return `
        <button
          type="button"
          class="student-problem-tab${isActive ? " active" : ""}${submitted ? " submitted" : ""}"
          data-student-problem-id="${Number(problem.id)}"
        >
          <span>Q${index + 1}</span>
          <strong>${htmlEscape(problem.title)}</strong>
          <small>${submitted ? "Submitted" : "Open"}</small>
        </button>
      `;
    })
    .join("");
}

function resetResultPanel() {
  const scoreTitle = codingQs("[data-score-title]");
  const resultPanel = codingQs("[data-result-panel]");
  if (scoreTitle) scoreTitle.textContent = "No Run Yet";
  if (resultPanel) resultPanel.innerHTML = "";
}

function updateLanguageSelector(problem) {
  const select = codingQs("#languageSelect");
  if (!select || !problem || !Array.isArray(problem.enabled_languages)) return;

  const enabled = problem.enabled_languages;
  const available = new Set(enabled);
  const options = Array.from(select.options);

  options.forEach((option) => {
    const isEnabled = available.has(option.value);
    option.disabled = !isEnabled;
    option.hidden = !isEnabled;
  });

  if (!enabled.length) return;

  if (!available.has(codingState.currentLanguage)) {
    codingState.currentLanguage = enabled[0];
  }

  select.value = codingState.currentLanguage;
}

function loadMonaco() {
  if (window.monaco) return Promise.resolve(window.monaco);
  if (!window.require) {
    return Promise.reject(new Error("Monaco loader is unavailable."));
  }
  if (!codingState.monacoReady) {
    window.require.config({ paths: { vs: MONACO_CDN_VS } });
    codingState.monacoReady = new Promise((resolve, reject) => {
      window.require(["vs/editor/editor.main"], () => resolve(window.monaco), reject);
    });
  }
  return codingState.monacoReady;
}

function draftKey(language = codingState.currentLanguage, problem = codingState.problem) {
  const problemId = problem?.id || "unknown";
  return `examguard_code_${problemId}_${language}`;
}

function languageKey(problem = codingState.problem) {
  const problemId = problem?.id || "unknown";
  return `examguard_code_language_${problemId}`;
}

function starterCode(language = codingState.currentLanguage, problem = codingState.problem) {
  return problem?.starter_code?.[language] || "";
}

function savedLanguageForProblem(problem) {
  const saved = localStorage.getItem(languageKey(problem));
  if (saved && problem?.enabled_languages?.includes(saved)) return saved;
  if (problem?.enabled_languages?.includes(codingState.currentLanguage)) {
    return codingState.currentLanguage;
  }
  return problem?.enabled_languages?.[0] || "python";
}

function loadDraft(language = codingState.currentLanguage, problem = codingState.problem) {
  return localStorage.getItem(draftKey(language, problem)) || starterCode(language, problem);
}

function saveDraft() {
  if (!codingState.editor || !codingState.problem) return;
  localStorage.setItem(draftKey(), codingState.editor.getValue());
}

function serverDraftPayload() {
  if (!codingState.editor || !codingState.problem) return null;
  return {
    problem_id: codingState.problem.id,
    language: codingState.currentLanguage,
    source_code: codingState.editor.getValue(),
  };
}

async function saveServerDraft(options = {}) {
  if (!getToken() || codingState.examSubmitted || codingState.autoSubmitted) return false;
  const payload = serverDraftPayload();
  if (!payload) return false;

  const signature = `${payload.problem_id}:${payload.language}:${payload.source_code}`;
  if (!options.force && signature === codingState.lastServerDraftSignature) {
    return true;
  }
  if (codingState.draftSaveInFlight && !options.keepalive) return false;

  const body = JSON.stringify(payload);
  const useKeepalive = Boolean(options.keepalive && body.length < 60000);
  codingState.draftSaveInFlight = true;
  try {
    const response = await fetch(`${CODING_API_BASE}/contest/draft`, {
      method: "PUT",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body,
      keepalive: useKeepalive,
    });
    if (!response.ok) return false;
    codingState.lastServerDraftSignature = signature;
    return true;
  } catch {
    return false;
  } finally {
    codingState.draftSaveInFlight = false;
  }
}

function scheduleServerDraftSave() {
  window.clearTimeout(codingState.serverDraftTimer);
  codingState.serverDraftTimer = window.setTimeout(() => {
    saveServerDraft().catch(() => undefined);
  }, 1500);
}

function startServerDraftSync() {
  if (codingState.serverDraftInterval) return;
  codingState.serverDraftInterval = window.setInterval(() => {
    saveServerDraft().catch(() => undefined);
  }, 10000);
}

function scheduleDraftSave() {
  window.clearTimeout(codingState.draftSaveTimer);
  codingState.draftSaveTimer = window.setTimeout(saveDraft, 400);
  scheduleServerDraftSave();
}

function notifyClipboardBlocked() {
  setContestStatus("Clipboard action blocked inside editor.", "warning");
}

function blockEditorClipboard(monaco, editor) {
  const blockedCodes = new Set([
    monaco.KeyCode.KeyC,
    monaco.KeyCode.KeyV,
    monaco.KeyCode.KeyX,
  ]);

  editor.onKeyDown((event) => {
    if ((event.ctrlKey || event.metaKey) && blockedCodes.has(event.keyCode)) {
      event.preventDefault();
      event.stopPropagation();
      notifyClipboardBlocked();
    }
  });

  editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyC, notifyClipboardBlocked);
  editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyV, notifyClipboardBlocked);
  editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyX, notifyClipboardBlocked);

  const editorNode = editor.getDomNode();
  ["copy", "cut", "paste", "contextmenu"].forEach((eventName) => {
    editorNode.addEventListener(eventName, (event) => {
      event.preventDefault();
      notifyClipboardBlocked();
    });
  });
}

function isCodingWorkspaceOpen() {
  const workspace = codingQs("[data-workspace]");
  return Boolean(workspace && !workspace.hidden && codingState.problem && !codingState.examSubmitted);
}

function blockPageClipboard() {
  ["copy", "cut", "paste"].forEach((eventName) => {
    document.addEventListener(eventName, (event) => {
      if (event.defaultPrevented || !isCodingWorkspaceOpen()) return;
      event.preventDefault();
      notifyClipboardBlocked();
    });
  });
}

async function ensureEditor() {
  const monaco = await loadMonaco();
  const editorHost = codingQs("#monacoEditor");
  if (codingState.editor) {
    return codingState.editor;
  }

  codingState.editor = monaco.editor.create(editorHost, {
    value: loadDraft(),
    language: "python",
    theme: "vs-dark",
    automaticLayout: true,
    minimap: { enabled: false },
    fontSize: 14,
    fontFamily: "JetBrains Mono, Consolas, monospace",
    scrollBeyondLastLine: false,
    contextmenu: false,
    tabSize: 4,
    readOnly: false,
  });
  codingState.editor.onDidChangeModelContent(scheduleDraftSave);
  blockEditorClipboard(monaco, codingState.editor);
  return codingState.editor;
}

function setEditorLanguage(language) {
  codingState.currentLanguage = language;
  if (codingState.problem) {
    localStorage.setItem(languageKey(), language);
  }
  if (!codingState.editor || !window.monaco) return;
  const monacoLanguage = {
    python: "python",
    cpp: "cpp",
    java: "java",
  }[language];
  window.monaco.editor.setModelLanguage(codingState.editor.getModel(), monacoLanguage);
}

async function changeLanguage(event) {
  saveDraft();
  saveServerDraft({ force: true }).catch(() => undefined);
  const language = event.currentTarget.value;
  setEditorLanguage(language);
  if (codingState.editor) {
    codingState.editor.setValue(loadDraft(language));
  }
}

function setEditorLocked(locked) {
  codingState.editorLocked = locked;
  if (codingState.editor) {
    codingState.editor.updateOptions({ readOnly: locked, domReadOnly: locked });
  }
  const busy = codingState.submitInFlight;
  codingQs("[data-run-samples]").disabled = locked || busy;
  codingQs("[data-submit-code]").disabled = locked || busy;
  codingQs("#languageSelect").disabled = locked || busy;
}

function setBusy(busy) {
  codingState.submitInFlight = busy;
  setEditorLocked(codingState.editorLocked);
}

async function activateProblem(problem, options = {}) {
  if (!problem) return;

  const previousProblemId = codingState.problem?.id;
  if (!options.skipSave && previousProblemId && previousProblemId !== problem.id) {
    saveDraft();
    saveServerDraft({ force: true }).catch(() => undefined);
  }

  codingState.problem = problem;
  codingState.currentLanguage = savedLanguageForProblem(problem);
  updateLanguageSelector(problem);
  renderProblem(problem);
  renderProblemTabs();

  const editor = await ensureEditor();
  setEditorLanguage(codingState.currentLanguage);
  if (previousProblemId !== problem.id || options.forceReload) {
    editor.setValue(loadDraft(codingState.currentLanguage, problem));
  }

  const storedResult = codingState.problemResults.get(problem.id);
  if (storedResult) {
    renderResults(storedResult);
  } else {
    resetResultPanel();
  }
  setEditorLocked(
    codingState.examSubmitted ||
      codingState.autoSubmitted ||
      isProblemSubmitted(problem.id)
  );
}

function nextOpenProblem(currentProblemId) {
  return codingState.problems.find((problem) => !isProblemSubmitted(problem.id) && problem.id !== currentProblemId)
    || codingState.problems.find((problem) => !isProblemSubmitted(problem.id))
    || null;
}

function startCountdown(targetIso, mode) {
  window.clearInterval(codingState.countdownTimer);

  const tick = () => {
    const remaining = targetIso ? secondsUntil(targetIso) : 0;
    const formatted = formatHms(remaining);
    const lockCountdown = codingQs("[data-lock-countdown]");
    const contestClock = codingQs("[data-contest-clock]");
    if (lockCountdown) lockCountdown.textContent = formatted;
    if (contestClock) contestClock.textContent = formatted;

    if (remaining > 0) return;
    window.clearInterval(codingState.countdownTimer);
    if (mode === "LOCKED") {
      fetchContestStatus();
    } else if (mode === "ACTIVE") {
      expireContest();
    }
  };

  tick();
  codingState.countdownTimer = window.setInterval(tick, 1000);
}

function showTimeoutModal() {
  setVisible(codingQs("[data-timeout-modal]"), true);
}

function expireContest() {
  if (codingState.autoSubmitted) return;
  codingState.autoSubmitted = true;
  setEditorLocked(true);
  showTimeoutModal();
  setContestStatus("Time expired. Automatic submission started.", "warning");
  autoSubmitCode();
}

function renderCaseCard(result) {
  const passed = result.status === "PASSED";
  const detail = result.visibility === "VISIBLE";
  return `
    <article class="case-card ${passed ? "passed" : "failed"}">
      <div class="case-head">
        <strong>${detail ? "Visible" : "Hidden"} Case ${Number(result.case_number)}</strong>
        <span>${htmlEscape(result.status)}</span>
      </div>
      ${
        detail
          ? `
            <label>Input</label>
            <pre>${htmlEscape(result.input_data || "")}</pre>
            <label>Expected</label>
            <pre>${htmlEscape(result.expected_output || "")}</pre>
            <label>Actual</label>
            <pre>${htmlEscape(result.actual_output || "")}</pre>
            ${
              result.error_logs
                ? `<label>Error Logs</label><pre>${htmlEscape(result.error_logs)}</pre>`
                : ""
            }
          `
          : ""
      }
    </article>
  `;
}

function renderResultGroup(title, results) {
  if (!results.length) return "";
  return `
    <section class="result-group">
      <h3>${htmlEscape(title)}</h3>
      ${results.map(renderCaseCard).join("")}
    </section>
  `;
}

function renderResults(data) {
  if (data.submitted) {
    codingState.latestFinalResult = data;
  }
  codingQs("[data-score-title]").textContent = data.submitted
    ? `Score ${Number(data.score).toFixed(2)} / 100`
    : `Samples ${Number(data.passed_cases)} / ${Number(data.total_cases)}`;
  codingQs("[data-result-panel]").innerHTML = [
    renderResultGroup("Visible Samples", data.visible_results || []),
    renderResultGroup("Hidden Cases", data.hidden_results || []),
  ].join("");
}

function submissionPayload(
  autoSubmitted = false,
  problem = codingState.problem,
  language = codingState.currentLanguage,
  sourceCode = null
) {
  if (problem?.id === codingState.problem?.id) {
    saveDraft();
  }
  return {
    problem_id: problem.id,
    language,
    source_code: sourceCode ?? codingState.editor.getValue(),
    auto_submitted: autoSubmitted,
  };
}

async function runSamples() {
  if (!codingState.problem || !codingState.editor) return;
  setBusy(true);
  setContestStatus("Running visible samples...");
  try {
    await saveServerDraft({ force: true });
    const data = await codingPost("/contest/run-samples", submissionPayload(false));
    codingState.problemResults.set(data.problem_id, data);
    renderResults(data);
    setContestStatus("Sample run complete.", "success");
  } catch (error) {
    setContestStatus(error.message, "warning");
  } finally {
    setBusy(false);
  }
}

async function submitCode(autoSubmitted = false) {
  if (!codingState.problem || !codingState.editor) return;
  if (codingState.submitInFlight) {
    window.setTimeout(() => submitCode(autoSubmitted), 1000);
    return;
  }

  setBusy(true);
  setContestStatus(autoSubmitted ? "Submitting automatically..." : "Submitting code...");
  try {
    await saveServerDraft({ force: true });
    const data = await codingPost("/contest/submit", submissionPayload(autoSubmitted));
    codingState.problemResults.set(data.problem_id, data);
    if (data.submitted) {
      codingState.submittedProblemIds.add(Number(data.problem_id));
    }
    renderResults(data);
    renderProblemTabs();
    if (data.submitted) {
      const finished = allProblemsSubmitted();
      setContestStatus(
        finished
          ? `All coding questions submitted. Latest score ${Number(data.score).toFixed(2)} / 100.`
          : `Question submitted. Score ${Number(data.score).toFixed(2)} / 100.`,
        "success"
      );

      if (finished || autoSubmitted) {
        codingState.examSubmitted = finished;
        codingState.editorLocked = true;
        codingState.emergencySubmitSent = true;
        window.dispatchEvent(
          new CustomEvent("examguard:exam-submitted", {
            detail: {
              autoSubmitted,
              submissionId: data.submission_id,
            },
          })
        );
        if (autoSubmitted) {
          showFinalResultScreen(Array.from(codingState.problemResults.values()));
        }
      } else {
        const nextProblem = nextOpenProblem(data.problem_id);
        if (nextProblem) {
          await activateProblem(nextProblem);
        } else {
          setEditorLocked(true);
        }
      }
    } else {
      setContestStatus("Submission saved.", "success");
    }
  } catch (error) {
    setContestStatus(error.message, "warning");
  } finally {
    setBusy(false);
    if (autoSubmitted || isProblemSubmitted(codingState.problem?.id)) {
      setEditorLocked(true);
    }
  }
}

async function autoSubmitAllProblems() {
  if (!codingState.problems.length) {
    await submitCode(true);
    return;
  }

  setBusy(true);
  const originalProblemId = codingState.problem?.id;
  const failures = [];
  try {
    saveDraft();
    await saveServerDraft({ force: true });

    for (const problem of codingState.problems) {
      if (isProblemSubmitted(problem.id)) continue;

      const language = savedLanguageForProblem(problem);
      const sourceCode = problem.id === codingState.problem?.id && codingState.editor
        ? codingState.editor.getValue()
        : loadDraft(language, problem);
      try {
        const data = await codingPost(
          "/contest/submit",
          submissionPayload(true, problem, language, sourceCode)
        );
        codingState.problemResults.set(data.problem_id, data);
        if (data.submitted) {
          codingState.submittedProblemIds.add(Number(data.problem_id));
        }
      } catch (error) {
        failures.push(error.message);
      }
    }
  } finally {
    setBusy(false);
  }

  renderProblemTabs();
  const currentResult = codingState.problemResults.get(originalProblemId);
  if (currentResult) renderResults(currentResult);
  codingState.examSubmitted = true;
  codingState.editorLocked = true;
  codingState.emergencySubmitSent = true;
  setEditorLocked(true);
  const results = Array.from(codingState.problemResults.values());
  if (results.length) {
    showFinalResultScreen(results);
  }
  setContestStatus(
    failures.length
      ? `Auto-submit finished with ${failures.length} issue(s).`
      : "Auto-submit completed for all open questions.",
    failures.length ? "warning" : "success"
  );
}

function autoSubmitCode() {
  autoSubmitAllProblems().catch((error) => {
    setContestStatus(error.message, "warning");
  });
}

function canEmergencyAutoSubmit() {
  return Boolean(
    getToken() &&
      codingState.problem &&
      codingState.editor &&
      !codingState.examSubmitted &&
      !codingState.autoSubmitted &&
      !codingState.emergencySubmitSent
  );
}

function emergencyAutoSubmit(reason = "pagehide") {
  if (!canEmergencyAutoSubmit()) return false;

  codingState.emergencySubmitSent = true;
  saveDraft();
  saveServerDraft({ force: true, keepalive: true }).catch(() => undefined);

  const body = JSON.stringify({
    problem_id: codingState.problem.id,
    reason,
  });
  fetch(`${CODING_API_BASE}/contest/auto-submit-draft`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body,
    keepalive: true,
  }).catch(() => undefined);
  setContestStatus("Auto-submit queued from saved draft.", "warning");
  return true;
}

async function renderActiveContest(data) {
  setExamActiveLock(true);
  if (!data.problem) {
    showLockedState({ ...data, status: "LOCKED", message: data.message });
    return;
  }

  if (!precheckComplete()) {
    codingState.pendingContestData = data;
    showPrecheckRequired();
    return;
  }

  codingState.pendingContestData = null;
  await ensureContestFullscreen("contest_active");
  renderFinalScore(null);
  setVisible(codingQs("[data-lock-screen]"), false);
  setVisible(codingQs("[data-workspace]"), true);
  const isNewProblem = codingState.problem?.id !== data.problem.id;
  codingState.problem = data.problem;

  updateLanguageSelector(data.problem);
  const activeLanguage = codingState.currentLanguage;
  if (activeLanguage && !data.problem.enabled_languages.includes(activeLanguage)) {
    codingState.currentLanguage = data.problem.enabled_languages[0];
  }

  renderProblem(data.problem);
  await ensureEditor();

  if (isNewProblem) {
    codingState.currentLanguage = codingQs("#languageSelect").value;
    setEditorLanguage(codingState.currentLanguage);
    codingState.editor.setValue(loadDraft());
  } else {
    const selected = codingQs("#languageSelect")?.value || codingState.currentLanguage;
    if (selected && data.problem.enabled_languages.includes(selected)) {
      codingState.currentLanguage = selected;
      setEditorLanguage(selected);
    }
  }

  if (!codingState.autoSubmitted && !codingState.examSubmitted) setEditorLocked(false);
  startServerDraftSync();
  saveServerDraft({ force: true }).catch(() => undefined);
  setContestStatus("Contest active.");
  startCountdown(data.end_time, "ACTIVE");
}

async function fetchContestStatus() {
  if (!getToken()) {
    if (window.ExamGuardInviteGate?.isActive?.()) {
      setContestStatus("Enter the generated PIN to unlock this exam.", "warning");
      return;
    }
    showAccessRequired();
    return;
  }

  try {
    const data = await codingGet("/contest/status");
    syncServerClock(data.server_time);
    setExamActiveLock(data.status === "ACTIVE");

    if (data.status === "ACTIVE") {
      await renderActiveContest(data);
      return;
    }

    if (data.status === "LOCKED" && !precheckComplete()) {
      codingState.pendingContestData = data;
      showPrecheckRequired();
      return;
    }

    if (data.status === "ENDED") {
      if (codingState.problem && codingState.editor && !codingState.autoSubmitted) {
        expireContest();
        return;
      } else {
        setEditorLocked(true);
      }
    }
    showLockedState(data);
  } catch (error) {
    setContestStatus(error.message, "warning");
    if (error.message.toLowerCase().includes("token")) {
      showAccessRequired();
    }
  }
}

function startStatusPolling() {
  window.clearInterval(codingState.statusTimer);
  codingState.statusTimer = window.setInterval(fetchContestStatus, 10000);
}

function initializeCodingContest() {
  if (!codingQs("[data-coding-contest]")) return;

  blockPageClipboard();
  codingQs("#languageSelect")?.addEventListener("change", changeLanguage);
  codingQs("[data-run-samples]")?.addEventListener("click", runSamples);
  codingQs("[data-submit-code]")?.addEventListener("click", () => submitCode(false));
  codingQs("[data-modal-close]")?.addEventListener("click", () => {
    setVisible(codingQs("[data-timeout-modal]"), false);
  });

  document.addEventListener("examguard:student-ready", () => {
    fetchContestStatus();
    startStatusPolling();
  });
  document.addEventListener("examguard:precheck-complete", () => {
    if (codingState.pendingContestData) {
      const pendingContestData = codingState.pendingContestData;
      if (pendingContestData.status === "ACTIVE") {
        renderActiveContest(pendingContestData);
      } else {
        showLockedState(pendingContestData);
        ensureContestFullscreen("precheck_complete_countdown").catch(() => undefined);
      }
    } else {
      fetchContestStatus();
    }
  });

  if (getToken()) {
    fetchContestStatus();
    startStatusPolling();
  } else if (window.ExamGuardInviteGate?.isActive?.()) {
    setVisible(codingQs("[data-lock-screen]"), false);
    setContestStatus("Enter the generated PIN to unlock this exam.", "warning");
  } else {
    showAccessRequired();
  }
}

window.addEventListener("pagehide", () => {
  emergencyAutoSubmit("pagehide");
});

window.addEventListener("beforeunload", (event) => {
  if (!emergencyAutoSubmit("beforeunload")) return;
  event.preventDefault();
  event.returnValue = "";
});

document.addEventListener("DOMContentLoaded", initializeCodingContest);
