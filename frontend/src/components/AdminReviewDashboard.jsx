import React, { useState, useMemo } from "react";
import {
  Shield,
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Eye,
  EyeOff,
  Users,
  UserX,
  Smartphone,
  Volume2,
  MicOff,
  Maximize2,
  Minimize2,
  ExternalLink,
  FileText,
  Download,
  Printer,
  Clock,
  Activity,
  Filter,
  Check,
  X,
  ChevronRight,
  Info,
  Lock,
  Camera,
} from "lucide-react";

// Mock candidate proctoring data demonstrating realistic multi-sensor telemetry & 50KB proof snapshots
const INITIAL_CANDIDATE_DATA = {
  candidateId: "cand_9f83a21e-7b4c",
  name: "Alex Rivera",
  rollNo: "CS-2026-089",
  email: "alex.rivera@university.edu",
  avatar: "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&auto=format&fit=crop&q=80",
  examId: "exam_cs301_finals",
  examTitle: "CS301: Advanced Data Structures & Algorithms",
  durationMinutes: 90,
  startedAt: "2026-11-03T09:00:15Z",
  submittedAt: "2026-11-03T10:24:45Z",
  status: "SUBMITTED",
  ipAddress: "198.51.100.42",
  networkIsp: "Campus Fiber Network - Zone B",
  userAgent: "Chrome 131.0.0 (Windows 11 64-bit)",
  screenResolution: "1920x1080",
  hasMultipleDisplays: false,
  baseTrustScore: 100,
  timeline: [
    {
      id: "v-001",
      timestamp: "2026-11-03T09:14:22Z",
      relativeTime: "+14m 07s",
      violationType: "GAZE_ANOMALY",
      category: "vision",
      severity: "medium",
      confidence: 0.91,
      penalty: 10,
      reviewStatus: "PENDING",
      examinerNotes: "",
      snapshot: "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='480' height='360' viewBox='0 0 480 360'><rect width='480' height='360' fill='%231e293b'/><circle cx='240' cy='180' r='70' fill='%23334155'/><circle cx='270' cy='165' r='12' fill='%2338bdf8'/><circle cx='220' cy='165' r='12' fill='%2338bdf8'/><path d='M200 220 Q240 240 280 220' stroke='%2394a3b8' stroke-width='4' fill='none'/><rect x='10' y='320' width='460' height='30' fill='rgba(0,0,0,0.7)'/><text x='20' y='340' fill='%2310b981' font-family='monospace' font-size='12'>EXAMGUARD PROCTOR PROOF • YAW: +36.4° • GAZE: RIGHT</text></svg>",
      metadata: {
        direction: "RIGHT",
        deltaYaw: 36.4,
        deltaPitch: -4.2,
        durationSeconds: 3.8,
        trigger: "Euler Angle Anomaly",
      },
    },
    {
      id: "v-002",
      timestamp: "2026-11-03T09:28:10Z",
      relativeTime: "+27m 55s",
      violationType: "TAB_SWITCH",
      category: "environment",
      severity: "medium",
      confidence: 1.0,
      penalty: 10,
      reviewStatus: "CONFIRMED",
      examinerNotes: "Switched to secondary Chrome window.",
      snapshot: "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='480' height='360' viewBox='0 0 480 360'><rect width='480' height='360' fill='%230f172a'/><rect x='40' y='40' width='400' height='260' rx='8' fill='%231e293b' stroke='%23ef4444' stroke-width='3'/><text x='140' y='170' fill='%23ef4444' font-family='sans-serif' font-size='20' font-weight='bold'>TAB VISIBILITY LOST</text><text x='160' y='200' fill='%2394a3b8' font-family='monospace' font-size='14'>visibilityState: hidden</text><rect x='10' y='320' width='460' height='30' fill='rgba(0,0,0,0.7)'/><text x='20' y='340' fill='%23ef4444' font-family='monospace' font-size='12'>EXAMGUARD LOCKDOWN EVENT • TAB_SWITCH</text></svg>",
      metadata: {
        trigger: "visibility_hidden",
        durationSeconds: 4.2,
      },
    },
    {
      id: "v-003",
      timestamp: "2026-11-03T09:42:05Z",
      relativeTime: "+41m 50s",
      violationType: "MULTIPLE_FACES",
      category: "vision",
      severity: "high",
      confidence: 0.96,
      penalty: 20,
      reviewStatus: "PENDING",
      examinerNotes: "",
      snapshot: "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='480' height='360' viewBox='0 0 480 360'><rect width='480' height='360' fill='%231e293b'/><circle cx='180' cy='180' r='60' fill='%23334155'/><circle cx='340' cy='150' r='45' fill='%23475569' stroke='%23ef4444' stroke-width='3'/><rect x='280' y='95' width='120' height='120' fill='none' stroke='%23ef4444' stroke-width='2' stroke-dasharray='4'/><text x='290' y='90' fill='%23ef4444' font-family='monospace' font-size='11'>SECOND_PERSON 96%</text><rect x='10' y='320' width='460' height='30' fill='rgba(0,0,0,0.7)'/><text x='20' y='340' fill='%23ef4444' font-family='monospace' font-size='12'>EXAMGUARD PROCTOR PROOF • 2 FACES DETECTED</text></svg>",
      metadata: {
        facesDetected: 2,
        primaryFaceConfidence: 0.98,
        secondaryFaceConfidence: 0.94,
        durationSeconds: 2.6,
      },
    },
    {
      id: "v-004",
      timestamp: "2026-11-03T09:55:18Z",
      relativeTime: "+55m 03s",
      violationType: "FULLSCREEN_EXIT",
      category: "environment",
      severity: "high",
      confidence: 1.0,
      penalty: 15,
      reviewStatus: "PENDING",
      examinerNotes: "",
      snapshot: "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='480' height='360' viewBox='0 0 480 360'><rect width='480' height='360' fill='%23090d16'/><rect x='80' y='70' width='320' height='200' rx='6' fill='%231e293b'/><circle cx='100' cy='90' r='5' fill='%23ef4444'/><circle cx='115' cy='90' r='5' fill='%23f59e0b'/><circle cx='130' cy='90' r='5' fill='%2310b981'/><text x='130' y='170' fill='%23f59e0b' font-family='sans-serif' font-size='18' font-weight='bold'>FULLSCREEN TERMINATED</text><text x='160' y='200' fill='%2394a3b8' font-family='monospace' font-size='13'>Exit Count: 1/3 Allowed</text><rect x='10' y='320' width='460' height='30' fill='rgba(0,0,0,0.7)'/><text x='20' y='340' fill='%23f59e0b' font-family='monospace' font-size='12'>EXAMGUARD LOCKDOWN • FULLSCREEN_EXIT #1</text></svg>",
      metadata: {
        exitAttempt: 1,
        maxAllowed: 3,
        trigger: "fullscreenchange",
      },
    },
    {
      id: "v-005",
      timestamp: "2026-11-03T10:11:40Z",
      relativeTime: "+1h 11m",
      violationType: "SPEECH_DETECTED",
      category: "audio",
      severity: "medium",
      confidence: 0.89,
      penalty: 10,
      reviewStatus: "DISMISSED",
      examinerNotes: "Candidate coughed and drank water. Background noise verified.",
      snapshot: "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='480' height='360' viewBox='0 0 480 360'><rect width='480' height='360' fill='%231e293b'/><path d='M80 180 Q120 120 160 180 T240 180 T320 180 T400 180' fill='none' stroke='%23f97316' stroke-width='4'/><rect x='180' y='80' width='120' height='40' rx='6' fill='%23f97316'/><text x='195' y='105' fill='%23ffffff' font-family='sans-serif' font-weight='bold' font-size='14'>67.4 dB SPIKE</text><rect x='10' y='320' width='460' height='30' fill='rgba(0,0,0,0.7)'/><text x='20' y='340' fill='%23f97316' font-family='monospace' font-size='12'>EXAMGUARD AUDIO SPECTRUM • 85-255Hz VOICE BAND</text></svg>",
      metadata: {
        decibels: 67.4,
        frequencyBandHz: "140Hz-220Hz",
        durationSeconds: 3.4,
      },
    },
  ],
};

export default function AdminReviewDashboard({
  candidateData = INITIAL_CANDIDATE_DATA,
  onSaveReview = null,
}) {
  const [data, setData] = useState(candidateData);
  const [activeFilter, setActiveFilter] = useState("ALL");
  const [selectedViolation, setSelectedViolation] = useState(null);
  const [examinerNoteInput, setExaminerNoteInput] = useState("");
  const [notification, setNotification] = useState(null);

  // Recalculate dynamic Trust Score strictly based on active confirmed/pending violations
  // (Dismissed false positives refund points back to candidate)
  const computedTrustScore = useMemo(() => {
    let totalPenalty = 0;
    data.timeline.forEach((item) => {
      if (item.reviewStatus !== "DISMISSED") {
        totalPenalty += item.penalty;
      }
    });
    return Math.max(0, 100 - totalPenalty);
  }, [data.timeline]);

  // Determine Trust Category & Color Theme
  const trustMeta = useMemo(() => {
    if (computedTrustScore >= 80) {
      return {
        label: "Verified Safe / High Integrity",
        color: "text-emerald-600 bg-emerald-50 border-emerald-300 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-800",
        badge: "bg-emerald-500",
        ringColor: "#10b981",
        icon: ShieldCheck,
      };
    } else if (computedTrustScore >= 50) {
      return {
        label: "Suspicious Activity / Under Audit",
        color: "text-amber-600 bg-amber-50 border-amber-300 dark:bg-amber-950/40 dark:text-amber-400 dark:border-amber-800",
        badge: "bg-amber-500",
        ringColor: "#f59e0b",
        icon: AlertTriangle,
      };
    } else {
      return {
        label: "Critical Breach / Recommended Disqualification",
        color: "text-rose-600 bg-rose-50 border-rose-300 dark:bg-rose-950/40 dark:text-rose-400 dark:border-rose-800",
        badge: "bg-rose-500",
        ringColor: "#ef4444",
        icon: ShieldAlert,
      };
    }
  }, [computedTrustScore]);

  // Filtered timeline stream
  const filteredTimeline = useMemo(() => {
    if (activeFilter === "ALL") return data.timeline;
    if (activeFilter === "VISION")
      return data.timeline.filter((v) => v.category === "vision");
    if (activeFilter === "ENVIRONMENT")
      return data.timeline.filter((v) => v.category === "environment");
    if (activeFilter === "AUDIO")
      return data.timeline.filter((v) => v.category === "audio");
    if (activeFilter === "FLAGGED")
      return data.timeline.filter((v) => v.reviewStatus !== "DISMISSED");
    return data.timeline;
  }, [data.timeline, activeFilter]);

  // Handle Examiner Review Decision
  const handleUpdateStatus = (violationId, newStatus) => {
    setData((prev) => ({
      ...prev,
      timeline: prev.timeline.map((v) =>
        v.id === violationId
          ? {
              ...v,
              reviewStatus: newStatus,
              examinerNotes: examinerNoteInput || v.examinerNotes,
            }
          : v
      ),
    }));

    if (selectedViolation && selectedViolation.id === violationId) {
      setSelectedViolation((prev) => ({
        ...prev,
        reviewStatus: newStatus,
        examinerNotes: examinerNoteInput || prev.examinerNotes,
      }));
    }

    setNotification(
      newStatus === "DISMISSED"
        ? "Violation marked as False Positive. Penalty points refunded!"
        : "Violation confirmed and locked into candidate record."
    );
    setTimeout(() => setNotification(null), 3500);

    if (onSaveReview) {
      onSaveReview({
        violationId,
        reviewStatus: newStatus,
        notes: examinerNoteInput,
      });
    }
  };

  // Export CSV Audit Trail
  const handleExportCSV = () => {
    const headers = [
      "Violation ID",
      "Timestamp (UTC)",
      "Relative Time",
      "Type",
      "Category",
      "Confidence",
      "Penalty Pts",
      "Review Status",
      "Examiner Notes",
    ];

    const rows = data.timeline.map((item) => [
      item.id,
      item.timestamp,
      item.relativeTime,
      item.violationType,
      item.category,
      `${Math.round(item.confidence * 100)}%`,
      item.penalty,
      item.reviewStatus,
      `"${(item.examinerNotes || "").replace(/"/g, '""')}"`,
    ]);

    const csvContent =
      "data:text/csv;charset=utf-8," +
      [headers.join(","), ...rows.map((e) => e.join(","))].join("\n");

    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute(
      "download",
      `ExamGuard_Audit_${data.rollNo}_${data.examId}.csv`
    );
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Trigger Print / PDF Export
  const handleExportPDF = () => {
    window.print();
  };

  const TrustIcon = trustMeta.icon;

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 p-4 md:p-8 font-sans antialiased">
      {/* Toast Notification */}
      {notification && (
        <div className="fixed bottom-6 right-6 z-50 flex items-center gap-3 bg-slate-900 text-white px-5 py-3 rounded-xl shadow-2xl border border-slate-700 animate-slide-up">
          <CheckCircle2 className="w-5 h-5 text-emerald-400" />
          <span className="text-sm font-medium">{notification}</span>
        </div>
      )}

      <div className="max-w-7xl mx-auto space-y-6">
        {/* Navigation / Header Actions */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
          <div>
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-indigo-600 dark:text-indigo-400">
              <Shield className="w-4 h-4" /> ExamGuard AI • Candidate Audit Console
            </div>
            <h1 className="text-2xl md:text-3xl font-bold tracking-tight mt-1">
              Integrity Review: {data.name}
            </h1>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleExportCSV}
              className="inline-flex items-center gap-2 px-3.5 py-2 text-sm font-medium text-slate-700 dark:text-slate-200 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition"
              title="Download CSV audit log"
            >
              <Download className="w-4 h-4" />
              <span>Export CSV</span>
            </button>
            <button
              onClick={handleExportPDF}
              className="inline-flex items-center gap-2 px-3.5 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow-sm transition"
              title="Print official departmental audit report"
            >
              <Printer className="w-4 h-4" />
              <span>Print / PDF</span>
            </button>
          </div>
        </div>

        {/* CANDIDATE OVERVIEW & TRUST SCORE HERO CARD */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Candidate Profile Details */}
          <div className="lg:col-span-2 bg-white dark:bg-slate-900 rounded-2xl p-6 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col justify-between">
            <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4 pb-5 border-b border-slate-100 dark:border-slate-800">
              <img
                src={data.avatar}
                alt={data.name}
                className="w-16 h-16 rounded-2xl object-cover ring-2 ring-indigo-500/20 shadow-md"
              />
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <h2 className="text-xl font-bold">{data.name}</h2>
                  <span className="text-xs px-2.5 py-0.5 rounded-full font-semibold bg-indigo-100 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-400">
                    {data.rollNo}
                  </span>
                  <span className="text-xs px-2.5 py-0.5 rounded-full font-semibold bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                    {data.status}
                  </span>
                </div>
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  {data.email} • Candidate ID: {data.candidateId}
                </p>
                <p className="text-xs font-medium text-slate-600 dark:text-slate-300">
                  {data.examTitle}
                </p>
              </div>
            </div>

            {/* Hardware & Environment Telemetry */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-5 text-xs text-slate-600 dark:text-slate-400">
              <div>
                <span className="block text-slate-400 dark:text-slate-500 font-medium">
                  IP & Geofence
                </span>
                <span className="font-semibold text-slate-800 dark:text-slate-200">
                  {data.ipAddress}
                </span>
              </div>
              <div>
                <span className="block text-slate-400 dark:text-slate-500 font-medium">
                  ISP & Zone
                </span>
                <span className="font-semibold text-slate-800 dark:text-slate-200 truncate block">
                  {data.networkIsp}
                </span>
              </div>
              <div>
                <span className="block text-slate-400 dark:text-slate-500 font-medium">
                  Display & Monitor
                </span>
                <span className="font-semibold text-slate-800 dark:text-slate-200">
                  {data.screenResolution} (Single Display)
                </span>
              </div>
              <div>
                <span className="block text-slate-400 dark:text-slate-500 font-medium">
                  Exam Timing
                </span>
                <span className="font-semibold text-slate-800 dark:text-slate-200">
                  84m 30s elapsed / 90m
                </span>
              </div>
            </div>
          </div>

          {/* DYNAMIC TRUST SCORE GAUGE */}
          <div
            className={`rounded-2xl p-6 border shadow-sm flex flex-col items-center justify-center text-center relative overflow-hidden ${trustMeta.color}`}
          >
            <div className="flex items-center gap-2 mb-2 font-semibold text-sm">
              <TrustIcon className="w-5 h-5" />
              <span>Trust Score Metric</span>
            </div>

            {/* Radial Percentage Display */}
            <div className="relative my-2 flex items-center justify-center">
              <div className="text-5xl md:text-6xl font-black tracking-tight">
                {computedTrustScore}%
              </div>
            </div>

            <p className="text-sm font-semibold mt-1">{trustMeta.label}</p>

            <div className="w-full mt-4 pt-4 border-t border-current/20 flex justify-around text-xs font-medium">
              <div>
                <span className="block text-current/70">Violations</span>
                <span className="font-bold text-base">{data.timeline.length}</span>
              </div>
              <div>
                <span className="block text-current/70">Points Lost</span>
                <span className="font-bold text-base">
                  -{100 - computedTrustScore}
                </span>
              </div>
              <div>
                <span className="block text-current/70">Unapproved Exits</span>
                <span className="font-bold text-base">
                  {data.timeline.filter((v) => v.violationType === "FULLSCREEN_EXIT").length}/3
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* TIMELINE CONTROLS & FILTER TABS */}
        <div className="bg-white dark:bg-slate-900 rounded-2xl p-5 border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Activity className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
              <h3 className="font-bold text-lg">Flagged Audit Timeline</h3>
              <span className="text-xs px-2.5 py-0.5 rounded-full font-medium bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
                {filteredTimeline.length} Incidents
              </span>
            </div>

            {/* Filter Chips */}
            <div className="flex flex-wrap items-center gap-1.5 text-xs font-medium">
              <button
                onClick={() => setActiveFilter("ALL")}
                className={`px-3 py-1.5 rounded-lg transition ${
                  activeFilter === "ALL"
                    ? "bg-indigo-600 text-white"
                    : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200"
                }`}
              >
                All Events
              </button>
              <button
                onClick={() => setActiveFilter("VISION")}
                className={`px-3 py-1.5 rounded-lg transition ${
                  activeFilter === "VISION"
                    ? "bg-indigo-600 text-white"
                    : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200"
                }`}
              >
                Visual AI (Gaze/Faces)
              </button>
              <button
                onClick={() => setActiveFilter("ENVIRONMENT")}
                className={`px-3 py-1.5 rounded-lg transition ${
                  activeFilter === "ENVIRONMENT"
                    ? "bg-indigo-600 text-white"
                    : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200"
                }`}
              >
                Environment & Tabs
              </button>
              <button
                onClick={() => setActiveFilter("AUDIO")}
                className={`px-3 py-1.5 rounded-lg transition ${
                  activeFilter === "AUDIO"
                    ? "bg-indigo-600 text-white"
                    : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200"
                }`}
              >
                Acoustic / Speech
              </button>
              <button
                onClick={() => setActiveFilter("FLAGGED")}
                className={`px-3 py-1.5 rounded-lg transition ${
                  activeFilter === "FLAGGED"
                    ? "bg-indigo-600 text-white"
                    : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200"
                }`}
              >
                Active Only
              </button>
            </div>
          </div>

          {/* CHRONOLOGICAL TIMELINE STREAM */}
          <div className="relative border-l-2 border-slate-200 dark:border-slate-800 ml-4 pl-6 space-y-6 pt-2">
            {filteredTimeline.map((item) => {
              const isDismissed = item.reviewStatus === "DISMISSED";
              const isConfirmed = item.reviewStatus === "CONFIRMED";

              return (
                <div
                  key={item.id}
                  className={`group relative bg-slate-50 dark:bg-slate-800/50 rounded-xl p-4 border transition-all hover:shadow-md cursor-pointer ${
                    isDismissed
                      ? "opacity-60 border-slate-200 dark:border-slate-800"
                      : isConfirmed
                      ? "border-emerald-300 dark:border-emerald-800 bg-emerald-50/20"
                      : "border-slate-300 dark:border-slate-700 hover:border-indigo-400"
                  }`}
                  onClick={() => {
                    setSelectedViolation(item);
                    setExaminerNoteInput(item.examinerNotes || "");
                  }}
                >
                  {/* Timeline bullet dot */}
                  <div
                    className={`absolute -left-[31px] top-5 w-4 h-4 rounded-full border-2 border-white dark:border-slate-900 ${
                      item.severity === "high"
                        ? "bg-rose-500"
                        : item.severity === "medium"
                        ? "bg-amber-500"
                        : "bg-blue-500"
                    }`}
                  />

                  <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                    <div className="space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        {/* Violation Type Badge */}
                        <span className="font-bold text-sm text-slate-900 dark:text-slate-100">
                          {formatViolationName(item.violationType)}
                        </span>

                        {/* Review Status Pill */}
                        <span
                          className={`text-xs px-2 py-0.5 rounded-full font-semibold ${
                            isDismissed
                              ? "bg-slate-200 dark:bg-slate-700 text-slate-600 dark:text-slate-300"
                              : isConfirmed
                              ? "bg-emerald-100 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-400"
                              : "bg-amber-100 dark:bg-amber-950/60 text-amber-700 dark:text-amber-400"
                          }`}
                        >
                          {item.reviewStatus}
                        </span>

                        {/* Severity chip */}
                        <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-rose-100 dark:bg-rose-950/60 text-rose-700 dark:text-rose-400">
                          -{item.penalty} pts
                        </span>

                        {/* Confidence score */}
                        <span className="text-xs text-slate-500 dark:text-slate-400">
                          Confidence: {Math.round(item.confidence * 100)}%
                        </span>
                      </div>

                      {/* Timestamp & Relative duration */}
                      <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                        <Clock className="w-3.5 h-3.5" />
                        <span>{item.relativeTime}</span>
                        <span>•</span>
                        <span>{new Date(item.timestamp).toLocaleTimeString()}</span>
                      </div>

                      {/* Sensor telemetry badge snippet */}
                      <p className="text-xs text-slate-600 dark:text-slate-300 mt-1">
                        {renderTelemetrySummary(item)}
                      </p>

                      {item.examinerNotes && (
                        <p className="text-xs italic text-indigo-600 dark:text-indigo-400 mt-1">
                          Note: "{item.examinerNotes}"
                        </p>
                      )}
                    </div>

                    {/* Snapshot Proof Thumbnail Chip */}
                    {item.snapshot && (
                      <div className="flex items-center gap-3">
                        <div className="relative group/thumb rounded-lg overflow-hidden border border-slate-300 dark:border-slate-700 w-24 h-16 bg-slate-900 shrink-0">
                          <img
                            src={item.snapshot}
                            alt="Incident snapshot proof"
                            className="w-full h-full object-cover transition group-hover/thumb:scale-105"
                          />
                          <div className="absolute inset-0 bg-black/40 opacity-0 group-hover/thumb:opacity-100 flex items-center justify-center transition">
                            <Eye className="w-4 h-4 text-white" />
                          </div>
                        </div>

                        <button
                          type="button"
                          className="px-3 py-1.5 text-xs font-semibold text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-950/40 rounded-lg hover:bg-indigo-100 transition flex items-center gap-1"
                        >
                          Verify Proof <ChevronRight className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* SNAPSHOT VERIFICATION MODAL DIALOG */}
      {selectedViolation && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in"
          role="dialog"
          aria-modal="true"
        >
          <div className="bg-white dark:bg-slate-900 rounded-2xl max-w-3xl w-full border border-slate-200 dark:border-slate-800 shadow-2xl overflow-hidden flex flex-col max-h-[92vh]">
            {/* Modal Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-800">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-xl bg-rose-100 dark:bg-rose-950/60 text-rose-600">
                  <Camera className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-bold text-lg">
                    Verify Proof Snapshot: {formatViolationName(selectedViolation.violationType)}
                  </h3>
                  <p className="text-xs text-slate-500">
                    Incident ID: {selectedViolation.id} • {selectedViolation.relativeTime} into exam
                  </p>
                </div>
              </div>

              <button
                onClick={() => setSelectedViolation(null)}
                className="p-2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 overflow-y-auto space-y-5">
              {/* High-Resolution Evidence Snapshot View (Max 50KB compressed WebP) */}
              <div className="relative rounded-xl overflow-hidden border border-slate-300 dark:border-slate-700 bg-slate-950 aspect-video flex items-center justify-center shadow-inner">
                {selectedViolation.snapshot ? (
                  <img
                    src={selectedViolation.snapshot}
                    alt="High-resolution violation snapshot evidence"
                    className="w-full h-full object-contain"
                  />
                ) : (
                  <div className="text-slate-500 text-sm flex flex-col items-center gap-2">
                    <AlertTriangle className="w-8 h-8 text-amber-500" />
                    <span>No snapshot proof attached to this event.</span>
                  </div>
                )}

                <div className="absolute top-3 left-3 bg-black/75 backdrop-blur-md px-3 py-1 rounded-md text-xs font-mono text-emerald-400 border border-emerald-500/30">
                  CONFIDENCE: {Math.round(selectedViolation.confidence * 100)}%
                </div>
              </div>

              {/* Multi-Sensor Telemetry & Details Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 text-xs">
                <div>
                  <span className="text-slate-400 block font-medium">Exact UTC Timestamp</span>
                  <span className="font-semibold">{selectedViolation.timestamp}</span>
                </div>
                <div>
                  <span className="text-slate-400 block font-medium">Penalty Weight</span>
                  <span className="font-semibold text-rose-500">-{selectedViolation.penalty} points</span>
                </div>
                <div>
                  <span className="text-slate-400 block font-medium">Current Status</span>
                  <span className="font-semibold">{selectedViolation.reviewStatus}</span>
                </div>
                <div>
                  <span className="text-slate-400 block font-medium">AI Sensor Model</span>
                  <span className="font-semibold">MediaPipe Vision Task (v0.10)</span>
                </div>
              </div>

              {/* Examiner Audit Notes Form */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block">
                  Examiner Audit Notes & Justification:
                </label>
                <textarea
                  value={examinerNoteInput}
                  onChange={(e) => setExaminerNoteInput(e.target.value)}
                  placeholder="Record your official audit note (e.g., 'False positive: candidate was adjusting eyeglasses' or 'Confirmed unauthorized notes on desk')."
                  className="w-full h-20 p-3 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 text-xs text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
            </div>

            {/* Modal Footer Review Actions */}
            <div className="flex flex-col sm:flex-row items-center justify-between gap-3 px-6 py-4 bg-slate-50 dark:bg-slate-800/40 border-t border-slate-200 dark:border-slate-800">
              <span className="text-xs text-slate-500">
                Action will immediately update the student's dynamic trust score.
              </span>

              <div className="flex items-center gap-2 w-full sm:w-auto">
                <button
                  type="button"
                  onClick={() => handleUpdateStatus(selectedViolation.id, "DISMISSED")}
                  className="flex-1 sm:flex-none px-4 py-2 text-xs font-semibold text-slate-700 dark:text-slate-200 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition flex items-center justify-center gap-1.5"
                >
                  <XCircle className="w-4 h-4 text-slate-400" />
                  Dismiss as False Positive (+{selectedViolation.penalty} pts)
                </button>

                <button
                  type="button"
                  onClick={() => handleUpdateStatus(selectedViolation.id, "CONFIRMED")}
                  className="flex-1 sm:flex-none px-4 py-2 text-xs font-semibold text-white bg-rose-600 hover:bg-rose-700 rounded-lg shadow-sm transition flex items-center justify-center gap-1.5"
                >
                  <CheckCircle2 className="w-4 h-4" />
                  Confirm Violation (-{selectedViolation.penalty} pts)
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function formatViolationName(type) {
  switch (type) {
    case "GAZE_ANOMALY":
    case "LOOKING_AWAY":
      return "Suspicious Gaze / Looking Away";
    case "MULTIPLE_FACES":
      return "Multiple Persons Detected in Frame";
    case "CANDIDATE_ABSENT":
    case "FACE_MISSING":
      return "Candidate Absent from Camera";
    case "TAB_SWITCH":
      return "Browser Tab Switched (Loss of Focus)";
    case "WINDOW_BLUR":
      return "Application Focus Lost (Window Blur)";
    case "FULLSCREEN_EXIT":
      return "Fullscreen Mode Terminated";
    case "SPEECH_DETECTED":
    case "ACOUSTIC_ACTIVITY":
      return "Speech / Acoustic Activity in Room";
    case "PROHIBITED_OBJECT":
    case "OBJECT_DETECTED":
      return "Prohibited Object Detected (Phone/Notes)";
    case "CLIPBOARD_VIOLATION":
      return "Clipboard Copy/Paste Blocked";
    default:
      return type.replace(/_/g, " ");
  }
}

function renderTelemetrySummary(item) {
  const m = item.metadata || {};
  switch (item.violationType) {
    case "GAZE_ANOMALY":
      return `Direction: ${m.direction || "AWAY"} | ΔYaw: ${m.deltaYaw || "+30"}° | Duration: ${m.durationSeconds || 3}s`;
    case "MULTIPLE_FACES":
      return `Detected Persons: ${m.facesDetected || 2} in camera field of view`;
    case "FULLSCREEN_EXIT":
      return `Unapproved Exit Attempt: ${m.exitAttempt || 1} of ${m.maxAllowed || 3} limit`;
    case "SPEECH_DETECTED":
      return `Acoustic Spike: ${m.decibels || 65}dB in human speech band (${m.frequencyBandHz || "85-255Hz"})`;
    case "TAB_SWITCH":
      return `Trigger: ${m.trigger || "visibilitychange"} | Duration away: ${m.durationSeconds || 2}s`;
    default:
      return `Confidence: ${Math.round(item.confidence * 100)}%`;
  }
}

