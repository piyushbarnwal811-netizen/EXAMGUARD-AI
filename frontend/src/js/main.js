function resolveApiBase() {
  const configured = localStorage.getItem("examguard_api_base");
  if (configured) return configured.replace(/\/$/, "");
  // Default to live Render backend for production (Vercel frontend)
  return "https://examguard-ai-317p.onrender.com/api";
}

const API_BASE = resolveApiBase();
window.EXAMGUARD_API_BASE = API_BASE;
let studentReadyNotified = false;
let generatedAiQuestions = [];
let adminProblemDrafts = [];
let activeProblemIndex = 0;

const qs = (selector) => document.querySelector(selector);

function getToken() {
  return localStorage.getItem("examguard_token") ||
         localStorage.getItem("token") ||
         localStorage.getItem("adminToken") ||
         "";
}

function clearStudentAccess() {
  localStorage.removeItem("examguard_token");
  localStorage.removeItem("token");
  localStorage.removeItem("adminToken");
  localStorage.removeItem("examguard_session_id");
  studentReadyNotified = false;
}

function authHeaders(extra = {}) {
  const headers = { ...extra };
  const token = getToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

function setStatus(message, type = "") {
  const status = qs("[data-status]");
  if (!status) return;
  status.className = `status ${type}`.trim();
  status.textContent = message;
}

function setExamStatus(message, type = "") {
  setStatus(message, type);
  const contestStatus = qs("[data-contest-status]");
  if (!contestStatus) return;
  contestStatus.className = `muted ${type}`.trim();
  contestStatus.textContent = message;
}

function saveToken(token, sessionId = null) {
  localStorage.setItem("examguard_token", token);
  localStorage.setItem("token", token);
  localStorage.setItem("adminToken", token);
  if (sessionId) {
    localStorage.setItem("examguard_session_id", String(sessionId));
  } else {
    localStorage.removeItem("examguard_session_id");
  }
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => {
    const entities = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#039;",
    };
    return entities[char];
  });
}

function errorMessageFromPayload(payload, fallback = "Request failed") {
  const detail = payload?.detail;
  if (typeof detail === "string") return detail;
  if (detail?.message) return detail.message;
  if (Array.isArray(detail) && detail.length) return detail[0].msg || fallback;
  return fallback;
}

function backendUnavailableMessage() {
  return `Backend unavailable at ${API_BASE}. Ensure the FastAPI server is running and reachable.`;
}

async function apiFetch(path, options = {}) {
  const maxTotalMs = 45000; // 45 seconds total backoff
  const start = Date.now();
  let attempt = 0;
  const token = getToken();
  const isFormData = options.body instanceof FormData;
  const defaultHeaders = {
    ...(!isFormData ? { 'Content-Type': 'application/json' } : {}),
    'Authorization': token ? `Bearer ${token}` : '',
    ...(options.headers || {})
  };
  const fetchOptions = { ...options, headers: defaultHeaders };
  while (true) {
    try {
      const response = await fetch(`${API_BASE}${path}`, fetchOptions);
      if (response.status === 503) {
        const elapsed = Date.now() - start;
        if (elapsed >= maxTotalMs) {
          return response; // give up, let caller handle
        }
        const delay = Math.min(1000 * Math.pow(2, attempt), 10000);
        await new Promise((r) => setTimeout(r, delay));
        attempt++;
        continue;
      }
      if (response.status === 401) {
        localStorage.removeItem('examguard_token');
        localStorage.removeItem('token');
        localStorage.removeItem('adminToken');
        localStorage.removeItem('examguard_session_id');
        window.location.href = 'login.html';
        return response;
      }
      return response;
    } catch {
      const elapsed = Date.now() - start;
      if (elapsed >= maxTotalMs) {
        throw new Error(backendUnavailableMessage());
      }
      const delay = Math.min(1000 * Math.pow(2, attempt), 10000);
      await new Promise((r) => setTimeout(r, delay));
      attempt++;
    }
  }
}

function getInviteTokenFromUrl() {
  const params = new URLSearchParams(window.location.search);
  return params.get("invite") || params.get("invite_token") || params.get("token");
}

function clearInviteTokenFromUrl() {
  const url = new URL(window.location.href);
  url.searchParams.delete("invite");
  url.searchParams.delete("invite_token");
  url.searchParams.delete("token");
  window.history.replaceState({}, document.title, `${url.pathname}${url.search}${url.hash}`);
}

async function postJson(path, payload) {
  const response = await apiFetch(path, {
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

async function putJson(path, payload) {
  const response = await apiFetch(path, {
    method: "PUT",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(errorMessageFromPayload(error));
  }

  return response.json();
}

async function getJson(path) {
  const response = await apiFetch(path, {
    headers: authHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(errorMessageFromPayload(error));
  }

  return response.json();
}

function notifyStudentReady() {
  if (studentReadyNotified) return;
  studentReadyNotified = true;
  window.ExamGuardTracking?.sendEvent?.(
    "EXAM_START",
    "Student exam context initialized.",
    { trigger: "student_ready" }
  );
  document.dispatchEvent(new CustomEvent("examguard:student-ready"));
}

function showExamAccessGate(message = "Open your exam invitation link to begin.") {
  const holder = qs("[data-question-list]");
  if (!holder) return;

  holder.innerHTML = `
    <article class="question-area">
      <h2>Invitation Required</h2>
      <p class="muted">${escapeHtml(message)}</p>
      <a class="button" href="login.html">Student Login</a>
    </article>
  `;
}

function setExamSurfaceForPinGate(active) {
  const cameraPanel = qs("[data-camera-panel]");
  if (cameraPanel) cameraPanel.hidden = active;

  [
    "[data-workspace]",
    "[data-lock-screen]",
    "[data-precheck-panel]",
  ].forEach((selector) => {
    const element = qs(selector);
    if (element && active) element.hidden = true;
  });

  const pinGate = qs("[data-invite-pin-gate]");
  if (pinGate) pinGate.hidden = !active;
}

function showInvitePinGate(isExamPage) {
  const inviteToken = getInviteTokenFromUrl();
  if (!inviteToken) return false;

  if (isExamPage) {
    clearStudentAccess();
    setExamSurfaceForPinGate(true);
    setExamStatus("Enter the generated PIN to unlock this exam.", "warning");
    const pinInput = qs("#invitePinForm input[name='pin']");
    window.setTimeout(() => pinInput?.focus(), 50);
    return true;
  }

  setExamStatus("Open the exam link and enter your generated PIN.", "warning");
  return true;
}

async function verifyInviteWithPin(event) {
  event.preventDefault();
  const inviteToken = getInviteTokenFromUrl();
  const form = event.currentTarget;
  const pin = form.pin.value.trim();

  if (!inviteToken) {
    setExamStatus("Invitation token is missing. Open a fresh exam link.", "warning");
    return;
  }

  setExamStatus("Verifying PIN...");
  try {
    const data = await postJson("/auth/verify-invite", { token: inviteToken, pin });
    saveToken(data.access_token, data.session_id);
    clearInviteTokenFromUrl();
    setExamSurfaceForPinGate(false);
    setExamStatus("PIN verified. Opening exam...", "success");

    const isQuestionExamPage = Boolean(qs("[data-question-list]"));
    const isCodingExamPage = Boolean(qs("[data-coding-contest]"));
    if (isQuestionExamPage) {
      await loadQuestions();
    }
    if (isCodingExamPage) {
      notifyStudentReady();
    }
  } catch (error) {
    setExamStatus(error.message, "warning");
  }
}

async function handleStudentLogin(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const rollNo = form.roll_no.value.trim();
  const pin = form.pin.value.trim();

  try {
    const data = await postJson("/auth/verify-pin", { roll_no: rollNo, pin });
    saveToken(data.access_token, data.session_id);
    setStatus("Login successful. Opening exam...", "success");
    window.location.href = "exam.html";
  } catch (error) {
    setStatus(error.message, "warning");
  }
}

async function handleAdminLogin(event) {
  event.preventDefault();
  const form = event.currentTarget;

  // Support both name="username" and name="email" for the identifier field
  const usernameInput = form.querySelector('[name="username"]') || form.querySelector('[name="email"]');
  const passwordInput = form.querySelector('[name="password"]');

  if (!usernameInput || !passwordInput) {
    setStatus("Login form is missing username/email or password fields.", "warning");
    return;
  }

  const username = usernameInput.value.trim();
  const password = passwordInput.value;

  if (!username || !password) {
    setStatus("Please enter both username/email and password.", "warning");
    return;
  }

  try {
    const data = await postJson("/auth/admin-login", {
      username,
      password,
    });
    saveToken(data.access_token);
    // Redirect to admin dashboard page
    window.location.href = "admin.html";
  } catch (error) {
    setStatus(error.message, "warning");
  }
}

async function loadQuestions() {
  const holder = qs("[data-question-list]");
  if (!holder) return;

  if (!getToken()) {
    showExamAccessGate();
    setStatus("Exam access requires your invitation link.", "warning");
    return;
  }

  const response = await apiFetch("/exam/questions", {
    headers: authHeaders(),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Questions could not be loaded." }));
    const message = errorMessageFromPayload(error, "Questions could not be loaded.");
    setStatus(message, "warning");
    if (response.status === 401 || response.status === 403) {
      showExamAccessGate("Your exam access token is invalid or expired. Open a fresh invitation link.");
    }
    return;
  }
  const questions = await response.json();

  holder.innerHTML = questions
    .map(
      (question) => `
        <article class="question-area">
          <h2>${question.id}. ${escapeHtml(question.question)}</h2>
          <div class="options">
            ${question.options
              .map(
                (option, index) => `
                  <label class="option">
                    <input
                      type="radio"
                      name="q${question.id}"
                      value="${String.fromCharCode(65 + index)}"
                      data-question-id="${question.id}"
                    />
                    ${escapeHtml(option)}
                  </label>
                `
              )
              .join("")}
          </div>
        </article>
      `
    )
    .join("");

  holder.querySelectorAll("input[type='radio']").forEach((input) => {
    input.addEventListener("change", submitAnswer);
  });
}

async function submitAnswer(event) {
  const input = event.currentTarget;
  const questionId = Number(input.dataset.questionId);

  try {
    await postJson("/exam/answers", {
      question_id: questionId,
      selected_option: input.value,
    });
    setStatus(`Answer saved for question ${questionId}.`, "success");
  } catch (error) {
    setStatus(error.message, "warning");
  }
}

function renderImportResult(data, targetSelector = "[data-import-result]") {
  const holder = qs(targetSelector);
  if (!holder || !data) return;

  const failures = data.failed_invites || [];
  const hasImportCounts = "inserted" in data || "updated" in data;
  holder.innerHTML = `
    <p><strong>Total:</strong> ${Number(data.total_students || 0)}</p>
    ${
      hasImportCounts
        ? `<p><strong>Inserted:</strong> ${Number(data.inserted || 0)} / <strong>Updated:</strong> ${Number(data.updated || 0)}</p>`
        : ""
    }
    <p><strong>Invites sent:</strong> ${Number(data.invites_sent || 0)} / <strong>Failed:</strong> ${Number(data.invites_failed || 0)}</p>
    ${
      failures.length
        ? `<ul>${failures
            .map(
              (item) =>
                `<li>${escapeHtml(item.email)}: ${escapeHtml(item.error)}</li>`
            )
            .join("")}</ul>`
        : ""
    }
  `;
}

async function uploadCsv(event) {
  event.preventDefault();
  const fileInput = qs("#studentsCsv");
  if (!fileInput?.files?.length) {
    setStatus("Please choose a CSV or Excel file.", "warning");
    return;
  }

  const formData = new FormData();
  formData.append("file", fileInput.files[0]);
  formData.append("send_invites", qs("#sendInvitesOnUpload")?.checked ? "true" : "false");

  const response = await apiFetch("/admin/import-students", {
    method: "POST",
    headers: authHeaders(),
    body: formData,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Upload failed" }));
    throw new Error(errorMessageFromPayload(error, "Upload failed"));
  }
  const data = await response.json();
  renderImportResult(data);
  setStatus(
    `Students imported. Inserted: ${data.inserted}, updated: ${data.updated}, invites sent: ${data.invites_sent}.`,
    "success"
  );
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function filenameFromDisposition(headerValue, fallback) {
  if (!headerValue) return fallback;
  const utfMatch = headerValue.match(/filename\*=UTF-8''([^;]+)/i);
  if (utfMatch) return decodeURIComponent(utfMatch[1].replaceAll('"', ""));
  const match = headerValue.match(/filename="?([^";]+)"?/i);
  return match ? match[1] : fallback;
}

function safeFilenamePart(value) {
  return String(value || "Exam").replace(/[^A-Za-z0-9]+/g, "_").replace(/^_+|_+$/g, "") || "Exam";
}

function formatDateTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return date.toLocaleString();
}

function renderExamHistory(exams) {
  const holder = qs("[data-exam-history]");
  if (!holder) return;

  if (!Array.isArray(exams) || !exams.length) {
    holder.innerHTML = `
      <tr>
        <td class="table-empty" colspan="6">No exams scheduled.</td>
      </tr>
    `;
    return;
  }

  holder.innerHTML = exams
    .map((exam) => {
      const fallbackName = `Exam_Report_${Number(exam.id)}_${safeFilenamePart(exam.title)}.xlsx`;
      return `
        <tr>
          <td>
            <strong>${escapeHtml(exam.title)}</strong>
            <p class="muted">ID ${Number(exam.id)}${exam.is_published ? "" : " / unpublished"}</p>
          </td>
          <td>${escapeHtml(formatDateTime(exam.start_time))}</td>
          <td>${escapeHtml(formatDateTime(exam.end_time))}</td>
          <td>${escapeHtml(exam.status)}</td>
          <td>${Number(exam.students_submitted || 0)} students / ${Number(exam.total_submissions || 0)} submissions</td>
          <td>
            <button
              type="button"
              class="table-action"
              data-download-exam-report="${Number(exam.id)}"
              data-report-filename="${escapeHtml(fallbackName)}"
            >
              Download
            </button>
          </td>
        </tr>
      `;
    })
    .join("");
}

async function loadExamHistory() {
  if (!qs("[data-exam-history]") || !getToken()) return;

  try {
    const data = await getJson("/admin/exam-history");
    renderExamHistory(data);
  } catch (error) {
    renderExamHistory([]);
    setStatus(error.message, "warning");
  }
}

async function generatePins() {
  try {
    const data = await postJson("/admin/generate-pins", {});
    const header = "roll_no,name,email,pin";
    const rows = data.pins.map((item) =>
      [item.roll_no, item.name, item.email, item.pin]
        .map((value) => `"${String(value).replaceAll('"', '""')}"`)
        .join(",")
    );
    downloadBlob(
      new Blob([[header, ...rows].join("\n")], { type: "text/csv" }),
      "ExamGuard_PINs.csv"
    );
    setStatus(`Generated ${data.total_students} student PINs.`, "success");
  } catch (error) {
    setStatus(error.message, "warning");
  }
}

async function sendInvites() {
  try {
    const data = await postJson("/admin/send-invites", {});
    renderImportResult(data, "[data-invite-result]");
    setStatus(
      `Invites sent: ${data.invites_sent}, failed: ${data.invites_failed}.`,
      data.invites_failed ? "warning" : "success"
    );
  } catch (error) {
    setStatus(error.message, "warning");
  }
}

async function downloadReport(contestId = null, fallbackFilename = "Exam_Report.xlsx") {
  try {
    const query = contestId ? `?contest_id=${encodeURIComponent(contestId)}` : "";
    const response = await apiFetch(`/admin/export${query}`, {
      headers: authHeaders(),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Export failed" }));
      throw new Error(errorMessageFromPayload(error, "Export failed"));
    }
    const blob = await response.blob();
    const filename = filenameFromDisposition(
      response.headers.get("content-disposition"),
      fallbackFilename
    );
    downloadBlob(blob, filename);
    setStatus("Report downloaded.", "success");
  } catch (error) {
    setStatus(error.message, "warning");
  }
}

function toDatetimeLocal(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
  return date.toISOString().slice(0, 16);
}

function defaultContestSchedule() {
  const start = new Date();
  start.setMinutes(start.getMinutes() + 60);
  start.setSeconds(0, 0);
  const end = new Date(start);
  end.setHours(end.getHours() + 1);

  return {
    title: "ExamGuard Pro Coding Contest",
    start_time: start.toISOString(),
    end_time: end.toISOString(),
    is_published: false,
    server_time: "",
    status: "Not saved",
    remaining_seconds: null,
  };
}

function renderSchedule(data, options = {}) {
  const titleInput = qs("#contestTitle");
  const startInput = qs("#contestStartTime");
  const endInput = qs("#contestEndTime");
  const publishedInput = qs("#contestPublished");
  const summary = qs("[data-schedule-summary]");
  if (!data || !titleInput || !startInput || !endInput || !publishedInput) return;

  titleInput.value = data.title || "";
  startInput.value = toDatetimeLocal(data.start_time);
  endInput.value = toDatetimeLocal(data.end_time);
  publishedInput.checked = Boolean(data.is_published);

  if (summary) {
    const serverTime = data.server_time ? new Date(data.server_time) : null;
    const serverTimeText = serverTime && !Number.isNaN(serverTime.getTime())
      ? serverTime.toLocaleString()
      : "";
    const remainingSeconds = Number(data.remaining_seconds);
    summary.innerHTML = `
      <p><strong>Status:</strong> ${escapeHtml(options.statusLabel || data.status || "Not saved")}</p>
      ${options.message ? `<p>${escapeHtml(options.message)}</p>` : ""}
      ${serverTimeText ? `<p><strong>Server time:</strong> ${escapeHtml(serverTimeText)}</p>` : ""}
      ${Number.isFinite(remainingSeconds) ? `<p><strong>Remaining seconds:</strong> ${remainingSeconds}</p>` : ""}
    `;
  }
}

async function loadContestSchedule() {
  if (!qs("#contestScheduleForm")) return null;
  if (!getToken()) {
    renderSchedule(defaultContestSchedule(), {
      statusLabel: "Draft",
      message: "Login as admin before saving this schedule.",
    });
    return null;
  }

  try {
    const data = await getJson("/contest/schedule");
    renderSchedule(data);
    return data;
  } catch (error) {
    renderSchedule(defaultContestSchedule(), {
      statusLabel: "Not saved",
      message: "No schedule is saved yet. Review this draft and save it to create the contest.",
    });
    return null;
  }
}

async function saveContestSchedule(event) {
  event.preventDefault();
  const title = qs("#contestTitle")?.value.trim();
  const startTime = qs("#contestStartTime")?.value;
  const endTime = qs("#contestEndTime")?.value;
  const isPublished = Boolean(qs("#contestPublished")?.checked);

  if (!title || !startTime || !endTime) {
    setStatus("Please fill the contest schedule.", "warning");
    return;
  }

  const startDate = new Date(startTime);
  const endDate = new Date(endTime);
  if (Number.isNaN(startDate.getTime()) || Number.isNaN(endDate.getTime())) {
    setStatus("Please enter a valid contest time window.", "warning");
    return;
  }
  if (endDate <= startDate) {
    setStatus("End time must be after start time.", "warning");
    return;
  }

  const data = await putJson("/contest/schedule", {
    title,
    start_time: startDate.toISOString(),
    end_time: endDate.toISOString(),
    is_published: isPublished,
  });
  renderSchedule(data);
  setStatus("Contest schedule saved.", "success");
  await loadExamHistory();
}

function defaultProblemData() {
  return {
    enabled_languages: ["python", "cpp", "java"],
    title: "Sum of Two Numbers",
    statement: "Given two integers A and B, read them from standard input and print their sum.",
    input_format: "The input contains two integers A and B separated by whitespace.",
    output_format: "Print a single integer: A + B.",
    constraints: "-1000000 <= A, B <= 1000000",
    starter_code_python:
      "import sys\n\n" +
      "def solve():\n" +
      "    data = sys.stdin.read().strip().split()\n" +
      "    a, b = map(int, data[:2])\n" +
      "    print(a + b)\n\n" +
      "if __name__ == \"__main__\":\n" +
      "    solve()\n",
    starter_code_cpp:
      "#include <bits/stdc++.h>\n" +
      "using namespace std;\n\n" +
      "int main() {\n" +
      "    long long a, b;\n" +
      "    cin >> a >> b;\n" +
      "    cout << a + b << '\\n';\n" +
      "    return 0;\n" +
      "}\n",
    starter_code_java:
      "import java.util.*;\n\n" +
      "public class Main {\n" +
      "    public static void main(String[] args) {\n" +
      "        Scanner sc = new Scanner(System.in);\n" +
      "        long a = sc.nextLong();\n" +
      "        long b = sc.nextLong();\n" +
      "        System.out.println(a + b);\n" +
      "    }\n" +
      "}\n",
    test_cases: [
      ["2 3", "5", true],
      ["100 250", "350", true],
      ["0 0", "0", false],
      ["-5 12", "7", false],
      ["999999 1", "1000000", false],
      ["-1000000 -1", "-1000001", false],
      ["42 -42", "0", false],
      ["123456 654321", "777777", false],
      ["-700000 300000", "-400000", false],
      ["1000000 1000000", "2000000", false],
    ].map(([input_data, expected_output, is_visible], index) => ({
      sort_order: index + 1,
      input_data,
      expected_output,
      is_visible,
    })),
  };
}

function genericStarterCode() {
  return {
    starter_code_python:
      "import sys\n\n" +
      "def solve():\n" +
      "    data = sys.stdin.read()\n" +
      "    # Write your solution here.\n" +
      "    pass\n\n" +
      "if __name__ == \"__main__\":\n" +
      "    solve()\n",
    starter_code_cpp:
      "#include <bits/stdc++.h>\n" +
      "using namespace std;\n\n" +
      "int main() {\n" +
      "    ios::sync_with_stdio(false);\n" +
      "    cin.tie(nullptr);\n" +
      "    // Write your solution here.\n" +
      "    return 0;\n" +
      "}\n",
    starter_code_java:
      "import java.io.*;\n" +
      "import java.util.*;\n\n" +
      "public class Main {\n" +
      "    public static void main(String[] args) throws Exception {\n" +
      "        // Write your solution here.\n" +
      "    }\n" +
      "}\n",
  };
}

function normalizeTestCases(testCases = []) {
  const defaults = defaultProblemData().test_cases;
  return Array.from({ length: 10 }, (_item, index) => {
    const existing = testCases[index] || defaults[index];
    return {
      sort_order: index + 1,
      input_data: existing?.input_data || "",
      expected_output: existing?.expected_output || "",
      is_visible: Boolean(existing?.is_visible),
    };
  });
}

function normalizeProblemDraft(problem = null, index = 0) {
  const base = defaultProblemData();
  const data = problem || base;
  return {
    ...base,
    ...data,
    id: data.id || null,
    order_index: Number(data.order_index || index + 1),
    enabled_languages: Array.isArray(data.enabled_languages) && data.enabled_languages.length
      ? data.enabled_languages
      : ["python", "cpp", "java"],
    test_cases: normalizeTestCases(data.test_cases || []),
  };
}

function readProblemFormDraft() {
  const testCases = Array.from({ length: 10 }, (_item, index) => ({
    sort_order: index + 1,
    input_data: qs(`[data-case-input="${index}"]`)?.value || "",
    expected_output: qs(`[data-case-output="${index}"]`)?.value || "",
    is_visible: Boolean(qs(`[data-case-visible="${index}"]`)?.checked),
  }));
  const enabledLanguages = [];
  if (qs("#enablePython")?.checked) enabledLanguages.push("python");
  if (qs("#enableCpp")?.checked) enabledLanguages.push("cpp");
  if (qs("#enableJava")?.checked) enabledLanguages.push("java");

  return {
    id: adminProblemDrafts[activeProblemIndex]?.id || null,
    order_index: activeProblemIndex + 1,
    title: qs("#problemTitle")?.value || "",
    statement: qs("#problemStatement")?.value || "",
    input_format: qs("#problemInputFormat")?.value || "",
    output_format: qs("#problemOutputFormat")?.value || "",
    constraints: qs("#problemConstraints")?.value || "",
    starter_code_python: qs("#starterPython")?.value || "",
    starter_code_cpp: qs("#starterCpp")?.value || "",
    starter_code_java: qs("#starterJava")?.value || "",
    enabled_languages: enabledLanguages,
    test_cases: testCases,
  };
}

function syncActiveProblemDraft() {
  if (!qs("#codingProblemForm") || !adminProblemDrafts.length) return;
  adminProblemDrafts[activeProblemIndex] = normalizeProblemDraft(
    readProblemFormDraft(),
    activeProblemIndex
  );
}

function renderProblemBank() {
  const holder = qs("[data-problem-bank]");
  if (!holder) return;

  holder.innerHTML = adminProblemDrafts
    .map((problem, index) => {
      const visibleCount = (problem.test_cases || []).filter((item) => item.is_visible).length;
      const title = problem.title?.trim() || `Question ${index + 1}`;
      const activeClass = index === activeProblemIndex ? " active" : "";
      return `
        <button type="button" class="problem-bank-item${activeClass}" data-select-problem="${index}">
          <span>Q${index + 1}</span>
          <strong>${escapeHtml(title)}</strong>
          <small>${(problem.test_cases || []).length} cases / ${visibleCount} visible</small>
        </button>
      `;
    })
    .join("");

  const removeButton = qs("[data-remove-problem]");
  if (removeButton) removeButton.disabled = adminProblemDrafts.length <= 1;
}

function setActiveProblemDraft(index) {
  if (index < 0 || index >= adminProblemDrafts.length) return;
  syncActiveProblemDraft();
  activeProblemIndex = index;
  setProblemForm(adminProblemDrafts[activeProblemIndex]);
  renderProblemBank();
}

function setProblemDrafts(problems = []) {
  adminProblemDrafts = (Array.isArray(problems) && problems.length ? problems : [defaultProblemData()])
    .map((problem, index) => normalizeProblemDraft(problem, index));
  activeProblemIndex = Math.min(activeProblemIndex, adminProblemDrafts.length - 1);
  setProblemForm(adminProblemDrafts[activeProblemIndex]);
  renderProblemBank();
}

function addProblemDraft(problem = null) {
  syncActiveProblemDraft();
  const draft = normalizeProblemDraft(problem || {
    ...defaultProblemData(),
    title: `Question ${adminProblemDrafts.length + 1}`,
  }, adminProblemDrafts.length);
  adminProblemDrafts.push(draft);
  activeProblemIndex = adminProblemDrafts.length - 1;
  setProblemForm(draft);
  renderProblemBank();
  qs("#problemTitle")?.focus();
}

function removeActiveProblemDraft() {
  if (adminProblemDrafts.length <= 1) {
    setStatus("At least one coding question is required.", "warning");
    return;
  }

  adminProblemDrafts.splice(activeProblemIndex, 1);
  activeProblemIndex = Math.min(activeProblemIndex, adminProblemDrafts.length - 1);
  setProblemForm(adminProblemDrafts[activeProblemIndex]);
  renderProblemBank();
  setStatus("Question removed. Save to update the contest.", "success");
}

function renderTestCaseInputs(testCases = []) {
  const holder = qs("[data-test-cases]");
  if (!holder) return;

  const defaults = defaultProblemData().test_cases;
  const cases = Array.from({ length: 10 }, (_item, index) => {
    const existing = testCases[index] || defaults[index];
    return {
      input_data: existing?.input_data || "",
      expected_output: existing?.expected_output || "",
      is_visible: Boolean(existing?.is_visible),
    };
  });

  holder.innerHTML = cases
    .map(
      (testCase, index) => `
        <section class="test-case">
          <strong>Case ${index + 1}</strong>
          <label>
            Input
            <textarea data-case-input="${index}" rows="3" required>${escapeHtml(testCase.input_data)}</textarea>
          </label>
          <label>
            Expected
            <textarea data-case-output="${index}" rows="3" required>${escapeHtml(testCase.expected_output)}</textarea>
          </label>
          <label class="check-row">
            <input data-case-visible="${index}" type="checkbox" ${testCase.is_visible ? "checked" : ""} />
            Visible sample
          </label>
        </section>
      `
    )
    .join("");
}

function setProblemForm(data) {
  const problem = data || defaultProblemData();
  if (!qs("#codingProblemForm")) return;

  const enabled = Array.isArray(problem.enabled_languages)
    ? problem.enabled_languages
    : ["python", "cpp", "java"];
  const selected = new Set(enabled);

  qs("#problemTitle").value = problem.title || "";
  qs("#problemStatement").value = problem.statement || "";
  qs("#problemInputFormat").value = problem.input_format || "";
  qs("#problemOutputFormat").value = problem.output_format || "";
  qs("#problemConstraints").value = problem.constraints || "";
  qs("#enablePython").checked = selected.has("python");
  qs("#enableCpp").checked = selected.has("cpp");
  qs("#enableJava").checked = selected.has("java");
  qs("#starterPython").value = problem.starter_code_python || "";
  qs("#starterCpp").value = problem.starter_code_cpp || "";
  qs("#starterJava").value = problem.starter_code_java || "";
  syncStarterVisibility();
  renderTestCaseInputs(problem.test_cases || []);
}

function syncStarterVisibility() {
  const mapping = {
    python: qs("#enablePython")?.checked,
    cpp: qs("#enableCpp")?.checked,
    java: qs("#enableJava")?.checked,
  };

  ["python", "cpp", "java"].forEach((language) => {
    const field = qs(`[data-language-field="${language}"]`);
    const textarea = qs(`#starter${language === "cpp" ? "Cpp" : language.charAt(0).toUpperCase() + language.slice(1)}`);
    if (!field || !textarea) return;

    const enabled = Boolean(mapping[language]);
    field.hidden = !enabled;
    textarea.disabled = !enabled;
    textarea.required = enabled;
    textarea.placeholder = enabled ? "Starter code" : "Language disabled";
  });
}

function renderProblemSummary(data) {
  const holder = qs("[data-problem-summary]");
  if (!holder || !data) return;

  const problems = Array.isArray(data) ? data : [data];
  const active = problems[activeProblemIndex] || problems[0] || {};
  const totalCases = problems.reduce(
    (total, problem) => total + (problem.test_cases || []).length,
    0
  );
  const visibleCount = problems.reduce(
    (total, problem) => total + (problem.test_cases || []).filter((item) => item.is_visible).length,
    0
  );
  const enabled = Array.isArray(active.enabled_languages)
    ? active.enabled_languages
    : ["python", "cpp", "java"];
  holder.innerHTML = `
    <p><strong>Questions:</strong> ${problems.length}</p>
    <p><strong>Selected:</strong> ${escapeHtml(active.title || "Question")}</p>
    <p><strong>Enabled languages:</strong> ${escapeHtml(enabled.join(", "))}</p>
    <p><strong>Test cases:</strong> ${totalCases} total / ${visibleCount} visible</p>
  `;
}

function normalizeGeneratedTestCases(question) {
  const rawCases = Array.isArray(question.test_cases) ? question.test_cases : [];
  const sampleInput = question.sample_input || "1";
  const sampleOutput = question.sample_output || "1";
  const cases = rawCases
    .filter((item) => item?.input_data && item?.expected_output)
    .slice(0, 10)
    .map((item, index) => ({
      sort_order: index + 1,
      input_data: String(item.input_data),
      expected_output: String(item.expected_output),
      is_visible: Boolean(item.is_visible),
    }));

  while (cases.length < 10) {
    cases.push({
      sort_order: cases.length + 1,
      input_data: sampleInput,
      expected_output: sampleOutput,
      is_visible: cases.length < 2,
    });
  }

  const visibleCount = cases.filter((item) => item.is_visible).length;
  if (visibleCount !== 2) {
    cases.forEach((item, index) => {
      item.is_visible = index < 2;
    });
  }
  return cases;
}

function generatedQuestionToProblem(question) {
  const base = defaultProblemData();
  const starters = genericStarterCode();
  return {
    ...base,
    title: question.title || "",
    statement: question.statement || "",
    input_format: question.input_format || "Read input from standard input as described in the problem statement.",
    output_format: question.output_format || "Print the required result to standard output.",
    constraints: question.constraints || "Use efficient logic suitable for the selected difficulty.",
    starter_code_python: question.starter_code_python || starters.starter_code_python,
    starter_code_cpp: question.starter_code_cpp || starters.starter_code_cpp,
    starter_code_java: question.starter_code_java || starters.starter_code_java,
    test_cases: normalizeGeneratedTestCases(question),
  };
}

function renderAiQuestionResults(questions = []) {
  const holder = qs("[data-ai-question-results]");
  const addAllButton = qs("[data-add-all-ai-questions]");
  if (addAllButton) addAllButton.hidden = !questions.length;
  if (!holder) return;

  if (!questions.length) {
    holder.innerHTML = "";
    return;
  }

  holder.innerHTML = questions
    .map(
      (question, index) => `
        <article class="ai-question-card">
          <div>
            <h4>${escapeHtml(question.title)}</h4>
            <p>${escapeHtml(question.statement)}</p>
            <div class="sample-grid">
              <label>Sample Input<pre>${escapeHtml(question.sample_input)}</pre></label>
              <label>Sample Output<pre>${escapeHtml(question.sample_output)}</pre></label>
            </div>
          </div>
          <div class="ai-question-actions">
            <button type="button" class="button-secondary" data-use-ai-question="${index}">Use</button>
            <button type="button" data-add-ai-question="${index}">Add</button>
          </div>
        </article>
      `
    )
    .join("");
}

async function generateAiQuestions(event) {
  event.preventDefault();
  const topic = qs("#aiTopic")?.value.trim();
  const difficulty = qs("#aiDifficulty")?.value;
  const count = Number(qs("#aiQuestionCount")?.value || 3);

  if (!topic) {
    setStatus("Please enter a topic for AI generation.", "warning");
    return;
  }

  const submitButton = event.currentTarget.querySelector("button[type='submit']");
  if (submitButton) {
    submitButton.disabled = true;
    submitButton.textContent = "Generating...";
  }

  try {
    const data = await postJson("/questions/generate", {
      topic,
      difficulty,
      count,
    });
    generatedAiQuestions = data.questions || [];
    renderAiQuestionResults(generatedAiQuestions);
    setStatus(`Generated ${generatedAiQuestions.length} question(s).`, "success");
  } catch (error) {
    setStatus(error.message, "warning");
  } finally {
    if (submitButton) {
      submitButton.disabled = false;
      submitButton.textContent = "Generate with AI";
    }
  }
}

function useAiQuestion(index) {
  const question = generatedAiQuestions[index];
  if (!question) return;

  const problem = normalizeProblemDraft(generatedQuestionToProblem(question), activeProblemIndex);
  adminProblemDrafts[activeProblemIndex] = problem;
  setProblemForm(problem);
  renderProblemBank();
  renderProblemSummary(adminProblemDrafts);
  setStatus("AI question loaded in the selected question slot.", "success");
  qs("#problemTitle")?.focus();
}

function addAiQuestion(index) {
  const question = generatedAiQuestions[index];
  if (!question) return;

  addProblemDraft(generatedQuestionToProblem(question));
  renderProblemSummary(adminProblemDrafts);
  setStatus("AI question added to the contest list.", "success");
}

function addAllAiQuestions() {
  if (!generatedAiQuestions.length) return;
  syncActiveProblemDraft();
  generatedAiQuestions.forEach((question) => {
    adminProblemDrafts.push(
      normalizeProblemDraft(generatedQuestionToProblem(question), adminProblemDrafts.length)
    );
  });
  activeProblemIndex = adminProblemDrafts.length - generatedAiQuestions.length;
  setProblemForm(adminProblemDrafts[activeProblemIndex]);
  renderProblemBank();
  renderProblemSummary(adminProblemDrafts);
  setStatus(`${generatedAiQuestions.length} AI question(s) added to the contest list.`, "success");
}

async function loadCodingProblem() {
  if (!qs("#codingProblemForm")) return null;
  if (!getToken()) {
    const fallback = normalizeProblemDraft(defaultProblemData(), 0);
    setProblemDrafts([fallback]);
    renderProblemSummary(adminProblemDrafts);
    return null;
  }

  try {
    const data = await getJson("/contest/problems-admin");
    setProblemDrafts(data);
    renderProblemSummary(adminProblemDrafts);
    return data;
  } catch (error) {
    const fallback = normalizeProblemDraft(defaultProblemData(), 0);
    setProblemDrafts([fallback]);
    renderProblemSummary(adminProblemDrafts);
    return null;
  }
}

function validateProblemDraft(problem, index = 0) {
  const label = `Question ${index + 1}`;
  const testCases = normalizeTestCases(problem.test_cases || []).map((item) => ({
    input_data: item.input_data.trim(),
    expected_output: item.expected_output.trim(),
    is_visible: Boolean(item.is_visible),
  }));
  const emptyCaseIndex = testCases.findIndex(
    (item) => !item.input_data || !item.expected_output
  );
  if (emptyCaseIndex !== -1) {
    throw new Error(`${label}, test case ${emptyCaseIndex + 1} needs input and expected output.`);
  }

  const visibleCount = testCases.filter((item) => item.is_visible).length;
  if (visibleCount !== 2) {
    throw new Error(`${label}: Exactly 2 test cases must be marked visible.`);
  }

  const enabledLanguages = Array.isArray(problem.enabled_languages)
    ? problem.enabled_languages
    : [];
  if (!enabledLanguages.length) {
    throw new Error(`${label}: Enable at least one language for the coding contest.`);
  }

  const payload = {
    id: problem.id || null,
    title: (problem.title || "").trim(),
    statement: (problem.statement || "").trim(),
    input_format: (problem.input_format || "").trim(),
    output_format: (problem.output_format || "").trim(),
    constraints: (problem.constraints || "").trim(),
    starter_code_python: enabledLanguages.includes("python") ? (problem.starter_code_python || "").trim() : "",
    starter_code_cpp: enabledLanguages.includes("cpp") ? (problem.starter_code_cpp || "").trim() : "",
    starter_code_java: enabledLanguages.includes("java") ? (problem.starter_code_java || "").trim() : "",
    enabled_languages: enabledLanguages,
    test_cases: testCases,
  };

  ["title", "statement", "input_format", "output_format", "constraints"].forEach((field) => {
    if (!payload[field]) {
      throw new Error(`${label}: ${field.replaceAll("_", " ")} is required.`);
    }
  });
  enabledLanguages.forEach((language) => {
    const key = `starter_code_${language === "cpp" ? "cpp" : language}`;
    if (!payload[key]) {
      throw new Error(`${label}: Starter code is required for ${language}.`);
    }
  });

  return payload;
}

function collectCodingProblemPayload() {
  syncActiveProblemDraft();
  return validateProblemDraft(adminProblemDrafts[activeProblemIndex], activeProblemIndex);
}

function collectCodingProblemsPayload() {
  syncActiveProblemDraft();
  return adminProblemDrafts.map((problem, index) => validateProblemDraft(problem, index));
}

async function saveCodingProblem(event) {
  event.preventDefault();
  const data = await putJson("/contest/problems-admin", {
    problems: collectCodingProblemsPayload(),
  });
  setProblemDrafts(data);
  renderProblemSummary(adminProblemDrafts);
  setStatus(`${adminProblemDrafts.length} coding question(s) saved.`, "success");
}

async function initializeAdminDashboard() {
  if (!qs("#adminLoginForm")) return;
  if (!getToken()) {
    window.location.href = 'admin-login.html';
    return;
  }
  await Promise.all([
    loadContestSchedule(),
    loadCodingProblem(),
    loadExamHistory(),
  ]);
}

async function initializeStudentAccess() {
  const isQuestionExamPage = Boolean(qs("[data-question-list]"));
  const isCodingExamPage = Boolean(qs("[data-coding-contest]"));
  const isExamPage = isQuestionExamPage || isCodingExamPage;
  const inviteToken = getInviteTokenFromUrl();

  if (isExamPage && window.ExamGuardTracking?.blockMobileExam?.("initialize_student_access")) {
    setStatus("Mobile and tablet devices are blocked for this exam.", "warning");
    return;
  }

  if (inviteToken) {
    showInvitePinGate(isExamPage);
    return;
  }

  if (isQuestionExamPage) {
    await loadQuestions();
  } else if (isCodingExamPage && getToken()) {
    notifyStudentReady();
  }
}

window.ExamGuardInviteGate = {
  isActive: () => Boolean(getInviteTokenFromUrl() && qs("[data-invite-pin-gate]")) && !getToken(),
};

document.addEventListener("DOMContentLoaded", () => {
  qs("#studentLoginForm")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    await handleStudentLogin(e);
  });
  qs("#invitePinForm")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    await verifyInviteWithPin(e);
  });
  qs("#adminLoginForm")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    await handleAdminLogin(e);
  });
  qs("#csvUploadForm")?.addEventListener("submit", async (event) => {
    try {
      await uploadCsv(event);
    } catch (error) {
      setStatus(error.message, "warning");
    }
  });
  qs("[data-generate-pins]")?.addEventListener("click", generatePins);
  qs("[data-send-invites]")?.addEventListener("click", sendInvites);
  qs("[data-download-report]")?.addEventListener("click", () => downloadReport());
  qs("[data-refresh-exam-history]")?.addEventListener("click", loadExamHistory);
  qs("[data-exam-history]")?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-download-exam-report]");
    if (!button) return;
    downloadReport(button.dataset.downloadExamReport, button.dataset.reportFilename);
  });
  qs("#contestScheduleForm")?.addEventListener("submit", async (event) => {
    try {
      await saveContestSchedule(event);
    } catch (error) {
      setStatus(error.message, "warning");
    }
  });
  qs("#enablePython")?.addEventListener("change", syncStarterVisibility);
  qs("#enableCpp")?.addEventListener("change", syncStarterVisibility);
  qs("#enableJava")?.addEventListener("change", syncStarterVisibility);
  qs("#aiQuestionForm")?.addEventListener("submit", generateAiQuestions);
  qs("[data-add-all-ai-questions]")?.addEventListener("click", addAllAiQuestions);
  qs("[data-ai-question-results]")?.addEventListener("click", (event) => {
    const useButton = event.target.closest("[data-use-ai-question]");
    if (useButton) {
      useAiQuestion(Number(useButton.dataset.useAiQuestion));
      return;
    }
    const addButton = event.target.closest("[data-add-ai-question]");
    if (addButton) {
      addAiQuestion(Number(addButton.dataset.addAiQuestion));
    }
  });
  qs("[data-add-problem]")?.addEventListener("click", () => addProblemDraft());
  qs("[data-remove-problem]")?.addEventListener("click", removeActiveProblemDraft);
  qs("[data-problem-bank]")?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-select-problem]");
    if (!button) return;
    setActiveProblemDraft(Number(button.dataset.selectProblem));
  });
  qs("#codingProblemForm")?.addEventListener("input", () => {
    syncActiveProblemDraft();
    renderProblemBank();
    renderProblemSummary(adminProblemDrafts);
  });
  qs("#codingProblemForm")?.addEventListener("submit", async (event) => {
    try {
      await saveCodingProblem(event);
    } catch (error) {
      setStatus(error.message, "warning");
    }
  });
  initializeAdminDashboard().catch(() => {});
  initializeStudentAccess();
});

window.addEventListener("pagehide", () => {
  if (!localStorage.getItem("examguard_session_id")) return;
  window.ExamGuardTracking?.sendEvent?.(
    "EXAM_END",
    "Student exam page hidden or closed.",
    { trigger: "pagehide" },
    { keepalive: true }
  );
});
