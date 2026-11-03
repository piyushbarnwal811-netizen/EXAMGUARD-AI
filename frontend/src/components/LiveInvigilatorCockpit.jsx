import React, { useState, useEffect, useMemo, useRef } from "react";
import {
  Shield,
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  Mic,
  MicOff,
  PauseCircle,
  PlayCircle,
  Slash,
  Eye,
  EyeOff,
  Users,
  Search,
  Filter,
  Volume2,
  Radio,
  RefreshCw,
  Clock,
  CheckCircle,
  XCircle,
  Maximize2,
  Minimize2,
  Wifi,
  WifiOff,
  AlertOctagon,
  MessageSquare,
  Sparkles,
} from "lucide-react";

// Pre-seeded candidates for realistic multi-candidate 1:50 cockpit demo & testing
const SEED_CANDIDATES = [
  {
    sessionId: "sess_01",
    candidateId: "cand_01",
    rollNo: "CS-2026-004",
    name: "Aarav Sharma",
    trustScore: 42,
    latestViolation: "MULTIPLE_FACES",
    thumbnailBase64: null,
    isFrozen: false,
    freezeReason: null,
    isTerminated: false,
    lastHeartbeat: new Date().toISOString(),
  },
  {
    sessionId: "sess_02",
    candidateId: "cand_02",
    rollNo: "CS-2026-012",
    name: "Beatriz Santos",
    trustScore: 55,
    latestViolation: "TAB_SWITCH",
    thumbnailBase64: null,
    isFrozen: false,
    freezeReason: null,
    isTerminated: false,
    lastHeartbeat: new Date().toISOString(),
  },
  {
    sessionId: "sess_03",
    candidateId: "cand_03",
    rollNo: "CS-2026-027",
    name: "Chen Wei",
    trustScore: 98,
    latestViolation: null,
    thumbnailBase64: null,
    isFrozen: false,
    freezeReason: null,
    isTerminated: false,
    lastHeartbeat: new Date().toISOString(),
  },
  {
    sessionId: "sess_04",
    candidateId: "cand_04",
    rollNo: "CS-2026-031",
    name: "Devon Miller",
    trustScore: 84,
    latestViolation: "GAZE_ANOMALY",
    thumbnailBase64: null,
    isFrozen: false,
    freezeReason: null,
    isTerminated: false,
    lastHeartbeat: new Date().toISOString(),
  },
  {
    sessionId: "sess_05",
    candidateId: "cand_05",
    rollNo: "CS-2026-045",
    name: "Elena Rostova",
    trustScore: 38,
    latestViolation: "SECONDARY_DISPLAY",
    thumbnailBase64: null,
    isFrozen: true,
    freezeReason: "Virtual display detected",
    isTerminated: false,
    lastHeartbeat: new Date().toISOString(),
  },
  {
    sessionId: "sess_06",
    candidateId: "cand_06",
    rollNo: "CS-2026-052",
    name: "Farhan Siddiqui",
    trustScore: 95,
    latestViolation: null,
    thumbnailBase64: null,
    isFrozen: false,
    freezeReason: null,
    isTerminated: false,
    lastHeartbeat: new Date().toISOString(),
  },
  {
    sessionId: "sess_07",
    candidateId: "cand_07",
    rollNo: "CS-2026-068",
    name: "Grace Hopper Jr.",
    trustScore: 100,
    latestViolation: null,
    thumbnailBase64: null,
    isFrozen: false,
    freezeReason: null,
    isTerminated: false,
    lastHeartbeat: new Date().toISOString(),
  },
  {
    sessionId: "sess_08",
    candidateId: "cand_08",
    rollNo: "CS-2026-074",
    name: "Hassan Al-Mansoor",
    trustScore: 68,
    latestViolation: "VOICE_ACTIVITY",
    thumbnailBase64: null,
    isFrozen: false,
    freezeReason: null,
    isTerminated: false,
    lastHeartbeat: new Date().toISOString(),
  },
];

export default function LiveInvigilatorCockpit({
  examId = "exam_default",
  apiBase = "/api",
}) {
  const [candidates, setCandidates] = useState(SEED_CANDIDATES);
  const [wsConnected, setWsConnected] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterMode, setFilterMode] = useState("ALL"); // ALL, CRITICAL (<60), WARNED (60-80), CLEAN (>80)
  const [activeCandidateModal, setActiveCandidateModal] = useState(null);
  
  // Voice Warning & Intervention State
  const [warnModalCandidate, setWarnModalCandidate] = useState(null);
  const [warningPreset, setWarningPreset] = useState("Keep your eyes on the screen.");
  const [customWarningText, setCustomWarningText] = useState("");
  const [isRecordingVoice, setIsRecordingVoice] = useState(false);
  const [recordedAudioBase64, setRecordedAudioBase64] = useState(null);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);

  // Freeze Modal State
  const [freezeModalCandidate, setFreezeModalCandidate] = useState(null);
  const [freezeReason, setFreezeReason] = useState("Live integrity verification");

  // Disqualification Modal State
  const [disqualifyCandidate, setDisqualifyCandidate] = useState(null);
  const [disqualifyReason, setDisqualifyReason] = useState("Excessive academic integrity violations");

  // WebSocket Ref
  const wsRef = useRef(null);

  // Connect to WebSocket Live Hub
  useEffect(() => {
    let reconnectTimeout = null;

    function connect() {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const host = window.location.host;
      const wsUrl = `${protocol}//${host}/api/ws/invigilator/${encodeURIComponent(
        examId
      )}?role=invigilator`;

      try {
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          setWsConnected(true);
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            handleWsMessage(data);
          } catch (err) {
            console.warn("Failed to parse WS payload:", err);
          }
        };

        ws.onclose = () => {
          setWsConnected(false);
          reconnectTimeout = setTimeout(connect, 3000);
        };

        ws.onerror = (err) => {
          console.warn("WebSocket error in Invigilator Cockpit:", err);
          ws.close();
        };
      } catch (e) {
        console.warn("WS Connection Error:", e);
      }
    }

    connect();

    return () => {
      clearTimeout(reconnectTimeout);
      if (wsRef.current) wsRef.current.close();
    };
  }, [examId]);

  // Handle incoming WS events
  function handleWsMessage(data) {
    if (data.type === "INITIAL_MATRIX_STATE") {
      if (data.candidates && data.candidates.length > 0) {
        setCandidates((prev) => {
          const map = new Map(prev.map((c) => [c.sessionId, c]));
          data.candidates.forEach((c) => map.set(c.sessionId, c));
          return Array.from(map.values());
        });
      }
    } else if (data.type === "CANDIDATE_HEARTBEAT") {
      const cand = data.candidate;
      if (!cand) return;
      setCandidates((prev) => {
        const index = prev.findIndex((c) => c.sessionId === cand.sessionId);
        if (index >= 0) {
          const updated = [...prev];
          updated[index] = { ...updated[index], ...cand };
          return updated;
        } else {
          return [cand, ...prev];
        }
      });
    } else if (data.type === "CANDIDATE_FREEZE_UPDATED") {
      setCandidates((prev) =>
        prev.map((c) =>
          c.sessionId === data.sessionId
            ? { ...c, isFrozen: data.isFrozen, freezeReason: data.reason }
            : c
        )
      );
    } else if (data.type === "CANDIDATE_TERMINATED") {
      setCandidates((prev) =>
        prev.map((c) =>
          c.sessionId === data.sessionId ? { ...c, isTerminated: true } : c
        )
      );
    }
  }

  // Smart Prioritization Sort: Low Trust (<60) or Active Violations bubble to top-left
  const sortedAndFilteredCandidates = useMemo(() => {
    let list = [...candidates];

    // Filter Query
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      list = list.filter(
        (c) =>
          c.name.toLowerCase().includes(q) ||
          c.rollNo.toLowerCase().includes(q) ||
          (c.latestViolation && c.latestViolation.toLowerCase().includes(q))
      );
    }

    // Filter Mode
    if (filterMode === "CRITICAL") {
      list = list.filter((c) => c.trustScore < 60 || c.latestViolation);
    } else if (filterMode === "WARNED") {
      list = list.filter((c) => c.trustScore >= 60 && c.trustScore < 80);
    } else if (filterMode === "CLEAN") {
      list = list.filter((c) => c.trustScore >= 80 && !c.latestViolation);
    }

    // Smart Prioritization Sort
    list.sort((a, b) => {
      // 1. Terminated candidates to the end
      if (a.isTerminated !== b.isTerminated) return a.isTerminated ? 1 : -1;

      // 2. Urgent candidates (score < 60 or active violation) bubble to the top
      const aUrgent = a.trustScore < 60 || a.latestViolation ? 1 : 0;
      const bUrgent = b.trustScore < 60 || b.latestViolation ? 1 : 0;
      if (bUrgent !== aUrgent) return bUrgent - aUrgent;

      // 3. Lowest trust score first
      return a.trustScore - b.trustScore;
    });

    return list;
  }, [candidates, searchQuery, filterMode]);

  // Invigilator Intervention: Audio Warning Dispatch
  async function dispatchAudioWarning() {
    if (!warnModalCandidate) return;
    const message = customWarningText.trim() || warningPreset;

    const payload = {
      type: "TRIGGER_AUDIO_ALERT",
      sessionId: warnModalCandidate.sessionId,
      message,
      audioBase64: recordedAudioBase64,
    };

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(payload));
    } else {
      // REST fallback
      fetch(`${apiBase}/v1/invigilator/${examId}/intervene`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "WARN",
          sessionId: warnModalCandidate.sessionId,
          message,
          audioBase64: recordedAudioBase64,
        }),
      }).catch(console.warn);
    }

    setWarnModalCandidate(null);
    setCustomWarningText("");
    setRecordedAudioBase64(null);
  }

  // Voice recording via MediaRecorder
  async function startVoiceRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioChunksRef.current = [];
      const recorder = new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };

      recorder.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: "audio/webm" });
        const reader = new FileReader();
        reader.onloadend = () => {
          setRecordedAudioBase64(reader.result);
        };
        reader.readAsDataURL(audioBlob);
        stream.getTracks().forEach((track) => track.stop());
      };

      recorder.start();
      setIsRecordingVoice(true);
    } catch (err) {
      alert("Microphone permission required for 1-way voice streaming.");
    }
  }

  function stopVoiceRecording() {
    if (mediaRecorderRef.current && isRecordingVoice) {
      mediaRecorderRef.current.stop();
      setIsRecordingVoice(false);
    }
  }

  // Invigilator Intervention: Toggle Session Freeze
  function dispatchToggleFreeze(candidate, reason) {
    const nextFreezeState = !candidate.isFrozen;
    const payload = {
      type: "TOGGLE_SESSION_FREEZE",
      sessionId: candidate.sessionId,
      isFrozen: nextFreezeState,
      reason: nextFreezeState ? reason || "Integrity verification check" : "",
    };

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(payload));
    }

    // Local optimistic update
    setCandidates((prev) =>
      prev.map((c) =>
        c.sessionId === candidate.sessionId
          ? { ...c, isFrozen: nextFreezeState, freezeReason: payload.reason }
          : c
      )
    );

    setFreezeModalCandidate(null);
  }

  // Invigilator Intervention: Disqualify / Force Terminate
  function dispatchForceTerminate(candidate, reason) {
    const payload = {
      type: "FORCE_TERMINATE",
      sessionId: candidate.sessionId,
      reason: reason || "Disqualified for exam violations.",
    };

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(payload));
    }

    setCandidates((prev) =>
      prev.map((c) =>
        c.sessionId === candidate.sessionId ? { ...c, isTerminated: true } : c
      )
    );

    setDisqualifyCandidate(null);
  }

  // Metrics
  const criticalCount = candidates.filter((c) => c.trustScore < 60).length;
  const activeCount = candidates.filter((c) => !c.isTerminated).length;
  const avgTrustScore = candidates.length
    ? Math.round(
        candidates.reduce((sum, c) => sum + c.trustScore, 0) / candidates.length
      )
    : 100;

  return (
    <div className="min-h-screen bg-[#070b14] text-slate-100 font-sans p-4 md:p-6 select-none">
      {/* Cockpit Header */}
      <header className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-5 border-b border-slate-800/80 mb-6">
        <div>
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-cyan-500/20 via-sky-500/10 to-indigo-500/20 border border-cyan-500/30 flex items-center justify-center text-cyan-400 shadow-[0_0_15px_rgba(6,182,212,0.15)]">
              <Radio className="w-5 h-5 animate-pulse" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl md:text-2xl font-bold tracking-tight text-white">
                  Live Invigilator Cockpit
                </h1>
                <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-cyan-950/80 border border-cyan-500/40 text-cyan-300">
                  1:50 MATRIX
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Real-time micro-stream telemetry &bull; Exam ID:{" "}
                <span className="font-mono text-slate-300">{examId}</span>
              </p>
            </div>
          </div>
        </div>

        {/* Live Status Cluster & Telemetry Counters */}
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900/90 border border-slate-800 text-xs">
            <Users className="w-3.5 h-3.5 text-cyan-400" />
            <span className="text-slate-400">Candidates:</span>
            <span className="font-semibold text-white">{activeCount} / 50</span>
          </div>

          <div
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs ${
              criticalCount > 0
                ? "bg-rose-950/40 border-rose-500/50 text-rose-300 animate-pulse"
                : "bg-slate-900/90 border-slate-800 text-slate-400"
            }`}
          >
            <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />
            <span>Critical Flagged:</span>
            <span className="font-bold text-white">{criticalCount}</span>
          </div>

          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900/90 border border-slate-800 text-xs">
            <Shield className="w-3.5 h-3.5 text-emerald-400" />
            <span className="text-slate-400">Avg Trust:</span>
            <span
              className={`font-semibold ${
                avgTrustScore >= 80
                  ? "text-emerald-400"
                  : avgTrustScore >= 60
                  ? "text-amber-400"
                  : "text-rose-400"
              }`}
            >
              {avgTrustScore}%
            </span>
          </div>

          <div
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-mono ${
              wsConnected
                ? "bg-emerald-950/40 border-emerald-500/40 text-emerald-400"
                : "bg-rose-950/40 border-rose-500/40 text-rose-400"
            }`}
          >
            {wsConnected ? (
              <Wifi className="w-3.5 h-3.5" />
            ) : (
              <WifiOff className="w-3.5 h-3.5" />
            )}
            <span>{wsConnected ? "STREAM LIVE" : "DISCONNECTED"}</span>
          </div>
        </div>
      </header>

      {/* Control Bar: Filters & Search */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 mb-6 bg-slate-900/60 p-3 rounded-xl border border-slate-800/80">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search candidate by name, roll no, or violation..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-slate-950/80 border border-slate-800 rounded-lg pl-9 pr-4 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition-colors"
          />
        </div>

        <div className="flex items-center gap-2 overflow-x-auto">
          <span className="text-xs text-slate-400 flex items-center gap-1">
            <Filter className="w-3.5 h-3.5" />
            Sort:
          </span>
          <button
            onClick={() => setFilterMode("ALL")}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              filterMode === "ALL"
                ? "bg-cyan-500 text-slate-950 font-semibold"
                : "bg-slate-800/70 text-slate-400 hover:text-white"
            }`}
          >
            All Candidates ({candidates.length})
          </button>
          <button
            onClick={() => setFilterMode("CRITICAL")}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 ${
              filterMode === "CRITICAL"
                ? "bg-rose-500 text-white font-semibold shadow-[0_0_12px_rgba(244,63,94,0.4)]"
                : "bg-slate-800/70 text-rose-400 hover:text-rose-300"
            }`}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-rose-400 animate-pulse"></span>
            Critical Alert ({candidates.filter((c) => c.trustScore < 60 || c.latestViolation).length})
          </button>
          <button
            onClick={() => setFilterMode("WARNED")}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              filterMode === "WARNED"
                ? "bg-amber-500 text-slate-950 font-semibold"
                : "bg-slate-800/70 text-amber-400 hover:text-amber-300"
            }`}
          >
            Suspicious (60-79%)
          </button>
          <button
            onClick={() => setFilterMode("CLEAN")}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              filterMode === "CLEAN"
                ? "bg-emerald-500 text-slate-950 font-semibold"
                : "bg-slate-800/70 text-emerald-400 hover:text-emerald-300"
            }`}
          >
            Clean (80-100%)
          </button>
        </div>
      </div>

      {/* 1:50 Real-Time Monitoring Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-3.5">
        {sortedAndFilteredCandidates.map((candidate) => {
          const isCritical = candidate.trustScore < 60 || Boolean(candidate.latestViolation);
          const isFrozen = candidate.isFrozen;
          const isTerminated = candidate.isTerminated;

          return (
            <div
              key={candidate.sessionId}
              className={`group relative rounded-xl bg-slate-900/90 border transition-all duration-300 flex flex-col overflow-hidden ${
                isTerminated
                  ? "border-red-900/40 opacity-40 bg-slate-950"
                  : isFrozen
                  ? "border-amber-500/70 shadow-[0_0_20px_rgba(245,158,11,0.25)] ring-1 ring-amber-500/50"
                  : isCritical
                  ? "border-rose-500/80 shadow-[0_0_25px_rgba(244,63,94,0.3)] ring-2 ring-rose-500/80 animate-pulse"
                  : "border-slate-800/90 hover:border-slate-700 hover:shadow-lg"
              }`}
            >
              {/* Card Header: Roll No & Trust Score Pill */}
              <div className="p-2.5 pb-2 flex items-center justify-between border-b border-slate-800/60 bg-slate-950/40">
                <div className="min-w-0 pr-2">
                  <span className="font-mono text-xs font-bold text-white tracking-tight truncate block">
                    {candidate.rollNo}
                  </span>
                  <span className="text-[11px] text-slate-400 truncate block">
                    {candidate.name}
                  </span>
                </div>

                <div
                  className={`px-2 py-0.5 rounded-full text-[11px] font-mono font-bold flex items-center gap-1 shrink-0 ${
                    isTerminated
                      ? "bg-slate-800 text-slate-400"
                      : candidate.trustScore >= 80
                      ? "bg-emerald-950/70 border border-emerald-500/40 text-emerald-400"
                      : candidate.trustScore >= 60
                      ? "bg-amber-950/70 border border-amber-500/40 text-amber-300"
                      : "bg-rose-950/80 border border-rose-500/50 text-rose-300 shadow-[0_0_8px_rgba(244,63,94,0.3)]"
                  }`}
                >
                  <Shield className="w-2.5 h-2.5" />
                  <span>{candidate.trustScore}%</span>
                </div>
              </div>

              {/* Micro-Stream Thumbnail / Live Canvas Placeholder */}
              <div className="relative aspect-[4/3] bg-slate-950 overflow-hidden flex items-center justify-center">
                {candidate.thumbnailBase64 ? (
                  <img
                    src={candidate.thumbnailBase64}
                    alt={candidate.name}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="w-full h-full flex flex-col items-center justify-center bg-slate-950 relative">
                    <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(56,189,248,0.06),transparent_70%)]"></div>
                    <div className="w-12 h-12 rounded-full bg-slate-800/80 border border-slate-700/80 flex items-center justify-center text-slate-400 font-bold text-sm tracking-widest z-10">
                      {candidate.name
                        .split(" ")
                        .map((p) => p[0])
                        .slice(0, 2)
                        .join("")}
                    </div>
                    <span className="text-[10px] text-slate-500 font-mono mt-2 z-10 flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping"></span>
                      POLLING (4.5s)
                    </span>
                  </div>
                )}

                {/* Overlaid Badges: Frozen or Terminated */}
                {isTerminated && (
                  <div className="absolute inset-0 bg-red-950/80 backdrop-blur-[2px] flex flex-col items-center justify-center text-center p-2 z-20">
                    <Slash className="w-7 h-7 text-rose-500 mb-1" />
                    <span className="text-[11px] font-bold text-rose-300 tracking-wider">
                      DISQUALIFIED
                    </span>
                  </div>
                )}

                {isFrozen && !isTerminated && (
                  <div className="absolute inset-0 bg-amber-950/75 backdrop-blur-[2px] flex flex-col items-center justify-center text-center p-2 z-20">
                    <PauseCircle className="w-7 h-7 text-amber-400 mb-1 animate-pulse" />
                    <span className="text-[11px] font-bold text-amber-300 tracking-wider">
                      SESSION FROZEN
                    </span>
                    <span className="text-[9px] text-amber-200/80 truncate max-w-[140px]">
                      {candidate.freezeReason || "Integrity verification"}
                    </span>
                  </div>
                )}

                {/* Violation Tag Overlay */}
                {candidate.latestViolation && !isTerminated && !isFrozen && (
                  <div className="absolute top-2 left-2 right-2 bg-rose-600/90 text-white text-[10px] font-bold px-2 py-0.5 rounded shadow-lg backdrop-blur-sm flex items-center gap-1 truncate z-10">
                    <AlertTriangle className="w-3 h-3 shrink-0" />
                    <span className="truncate">{candidate.latestViolation}</span>
                  </div>
                )}
              </div>

              {/* Quick Invigilator Action Toolbar */}
              <div className="p-2 border-t border-slate-800/80 bg-slate-950/60 mt-auto flex items-center gap-1.5">
                {/* 1. Voice Warning Button */}
                <button
                  type="button"
                  title="Issue Live Voice Warning"
                  disabled={isTerminated}
                  onClick={() => setWarnModalCandidate(candidate)}
                  className="flex-1 py-1.5 px-2 rounded-lg bg-sky-950/60 hover:bg-sky-900/80 border border-sky-500/30 text-sky-300 text-xs font-semibold flex items-center justify-center gap-1 transition-all disabled:opacity-40"
                >
                  <Volume2 className="w-3.5 h-3.5" />
                  <span>Warn</span>
                </button>

                {/* 2. Freeze / Resume Button */}
                <button
                  type="button"
                  title={isFrozen ? "Resume Session" : "Freeze Candidate Session"}
                  disabled={isTerminated}
                  onClick={() => {
                    if (isFrozen) {
                      dispatchToggleFreeze(candidate, "");
                    } else {
                      setFreezeModalCandidate(candidate);
                    }
                  }}
                  className={`py-1.5 px-2 rounded-lg text-xs font-semibold flex items-center justify-center transition-all disabled:opacity-40 ${
                    isFrozen
                      ? "bg-emerald-950/60 hover:bg-emerald-900 border border-emerald-500/40 text-emerald-300"
                      : "bg-amber-950/60 hover:bg-amber-900 border border-amber-500/40 text-amber-300"
                  }`}
                >
                  {isFrozen ? (
                    <PlayCircle className="w-3.5 h-3.5" />
                  ) : (
                    <PauseCircle className="w-3.5 h-3.5" />
                  )}
                </button>

                {/* 3. Disqualify Button */}
                <button
                  type="button"
                  title="Disqualify & Force Terminate"
                  disabled={isTerminated}
                  onClick={() => setDisqualifyCandidate(candidate)}
                  className="py-1.5 px-2 rounded-lg bg-rose-950/60 hover:bg-rose-900 border border-rose-500/40 text-rose-300 text-xs font-semibold flex items-center justify-center transition-all disabled:opacity-40"
                >
                  <Slash className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* MODAL 1: 1-Way Live Voice Warning Dialog */}
      {warnModalCandidate && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-sky-500/40 rounded-2xl max-w-lg w-full p-6 shadow-2xl relative">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-4">
              <div className="flex items-center gap-2">
                <Volume2 className="w-5 h-5 text-sky-400" />
                <h3 className="font-bold text-base text-white">
                  Issue Live Warning to Candidate
                </h3>
              </div>
              <button
                onClick={() => setWarnModalCandidate(null)}
                className="text-slate-400 hover:text-white p-1"
              >
                ✕
              </button>
            </div>

            <div className="mb-4 bg-slate-950/70 p-3 rounded-lg border border-slate-800 flex items-center justify-between">
              <div>
                <span className="font-mono text-xs text-sky-400 font-bold block">
                  {warnModalCandidate.rollNo}
                </span>
                <span className="text-sm font-semibold text-white">
                  {warnModalCandidate.name}
                </span>
              </div>
              <div className="text-right">
                <span className="text-xs text-slate-400 block">Trust Score</span>
                <span
                  className={`text-sm font-bold font-mono ${
                    warnModalCandidate.trustScore < 60
                      ? "text-rose-400"
                      : "text-amber-400"
                  }`}
                >
                  {warnModalCandidate.trustScore}%
                </span>
              </div>
            </div>

            {/* Warning Presets */}
            <label className="text-xs text-slate-300 font-semibold mb-2 block">
              Quick Voice Presets:
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mb-4">
              {[
                "Keep your eyes on the screen.",
                "Remove unauthorized headphones immediately.",
                "Face your webcam directly.",
                "Multiple people detected. Keep room clear.",
                "Do not switch tabs or windows.",
              ].map((preset) => (
                <button
                  key={preset}
                  type="button"
                  onClick={() => {
                    setWarningPreset(preset);
                    setCustomWarningText("");
                  }}
                  className={`text-left text-xs p-2.5 rounded-lg border transition-all ${
                    warningPreset === preset && !customWarningText
                      ? "bg-sky-950/80 border-sky-500 text-sky-200"
                      : "bg-slate-950/50 border-slate-800 text-slate-300 hover:border-slate-700"
                  }`}
                >
                  {preset}
                </button>
              ))}
            </div>

            {/* Custom Warning Input */}
            <label className="text-xs text-slate-300 font-semibold mb-2 block">
              Or Type Custom Warning (Spoken via Text-To-Speech):
            </label>
            <input
              type="text"
              placeholder="e.g. Roll 24, please put away your smartphone."
              value={customWarningText}
              onChange={(e) => setCustomWarningText(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-sky-500 mb-4"
            />

            {/* 1-Way Microphone Stream Recording */}
            <div className="mb-6 p-3 rounded-lg bg-slate-950/80 border border-slate-800 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Mic
                  className={`w-4 h-4 ${
                    isRecordingVoice ? "text-rose-400 animate-pulse" : "text-slate-400"
                  }`}
                />
                <div>
                  <span className="text-xs font-semibold text-slate-200 block">
                    {isRecordingVoice
                      ? "Recording live mic stream..."
                      : recordedAudioBase64
                      ? "Voice note ready to transmit"
                      : "Record Real Voice Note"}
                  </span>
                  <span className="text-[11px] text-slate-500">
                    Candidate's browser auto-plays the audio aloud
                  </span>
                </div>
              </div>

              {!isRecordingVoice ? (
                <button
                  type="button"
                  onClick={startVoiceRecording}
                  className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium"
                >
                  {recordedAudioBase64 ? "Re-record" : "Start Mic"}
                </button>
              ) : (
                <button
                  type="button"
                  onClick={stopVoiceRecording}
                  className="px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold animate-pulse"
                >
                  Stop Recording
                </button>
              )}
            </div>

            {/* Dispatch Buttons */}
            <div className="flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => setWarnModalCandidate(null)}
                className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={dispatchAudioWarning}
                className="px-5 py-2 rounded-lg bg-sky-500 hover:bg-sky-400 text-slate-950 text-xs font-bold shadow-[0_0_15px_rgba(56,189,248,0.3)] flex items-center gap-1.5"
              >
                <Volume2 className="w-4 h-4" />
                <span>Transmit Warning Aloud</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 2: Remote Session Freeze Confirmation */}
      {freezeModalCandidate && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-amber-500/50 rounded-2xl max-w-md w-full p-6 shadow-2xl">
            <div className="w-12 h-12 rounded-full bg-amber-500/20 border border-amber-500/40 flex items-center justify-center text-amber-400 mb-4 mx-auto">
              <PauseCircle className="w-6 h-6" />
            </div>
            <h3 className="text-lg font-bold text-white text-center mb-1">
              Freeze Examination Session?
            </h3>
            <p className="text-xs text-slate-400 text-center mb-4">
              The student's screen will be instantly locked with an integrity check modal.
              All inputs and typing will be paused.
            </p>

            <div className="mb-4 bg-slate-950 p-3 rounded-lg border border-slate-800 text-xs">
              <span className="text-slate-400">Target Candidate:</span>
              <div className="font-semibold text-white mt-0.5">
                {freezeModalCandidate.name} ({freezeModalCandidate.rollNo})
              </div>
            </div>

            <label className="text-xs text-slate-300 font-semibold mb-1.5 block">
              Reason for Freeze:
            </label>
            <input
              type="text"
              value={freezeReason}
              onChange={(e) => setFreezeReason(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs text-white mb-5 focus:outline-none focus:border-amber-500"
            />

            <div className="flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => setFreezeModalCandidate(null)}
                className="px-4 py-2 rounded-lg bg-slate-800 text-slate-300 text-xs font-medium"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() =>
                  dispatchToggleFreeze(freezeModalCandidate, freezeReason)
                }
                className="px-5 py-2 rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-bold"
              >
                Confirm Freeze
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 3: Instant Disqualification Dialog */}
      {disqualifyCandidate && (
        <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border-2 border-rose-500 rounded-2xl max-w-md w-full p-6 shadow-2xl">
            <div className="w-12 h-12 rounded-full bg-rose-500/20 border border-rose-500/40 flex items-center justify-center text-rose-400 mb-4 mx-auto">
              <AlertOctagon className="w-6 h-6" />
            </div>
            <h3 className="text-lg font-bold text-white text-center mb-1">
              Force Terminate & Disqualify?
            </h3>
            <p className="text-xs text-slate-400 text-center mb-4">
              This action is <span className="text-rose-400 font-bold">permanent</span>.
              The student's session will be submitted immediately and their account locked.
            </p>

            <div className="mb-4 bg-slate-950 p-3 rounded-lg border border-slate-800 text-xs">
              <span className="text-slate-400">Target Candidate:</span>
              <div className="font-semibold text-rose-300 mt-0.5">
                {disqualifyCandidate.name} ({disqualifyCandidate.rollNo})
              </div>
            </div>

            <label className="text-xs text-slate-300 font-semibold mb-1.5 block">
              Formal Disqualification Reason:
            </label>
            <input
              type="text"
              value={disqualifyReason}
              onChange={(e) => setDisqualifyReason(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs text-white mb-5 focus:outline-none focus:border-rose-500"
            />

            <div className="flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => setDisqualifyCandidate(null)}
                className="px-4 py-2 rounded-lg bg-slate-800 text-slate-300 text-xs font-medium"
              >
                Abort
              </button>
              <button
                type="button"
                onClick={() =>
                  dispatchForceTerminate(disqualifyCandidate, disqualifyReason)
                }
                className="px-5 py-2 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold shadow-[0_0_15px_rgba(244,63,94,0.4)]"
              >
                Confirm Disqualification
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

