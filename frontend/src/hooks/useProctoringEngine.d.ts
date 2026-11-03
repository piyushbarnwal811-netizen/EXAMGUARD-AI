export interface ProctoringEngineConfig {
  examId?: string;
  candidateId?: string;
  sessionId?: string;
  apiBaseUrl?: string;
  token?: string | null;
  penaltyWeights?: Record<string, number>;
  maxExits?: number;
  criticalTrustScore?: number;
  enableAudio?: boolean;
  enableObjectDetection?: boolean;
  targetFps?: number;
  onAutoSubmit?: (data: { reason: string; trustScore: number; exitCount?: number; violationCounts?: Record<string, number> }) => void;
  onViolation?: (violation: ProctoringViolationPayload) => void;
  onWarning?: (message: string) => void;
}

export interface ProctoringViolationPayload {
  candidateId: string;
  examId: string;
  sessionId: string | null;
  timestamp: string;
  violationType: string;
  confidence: number;
  snapshot: string | null;
  currentScore: number;
  metadata?: Record<string, any>;
}

export interface ProctoringStatus {
  isInitialized: boolean;
  isCalibrating: boolean;
  calibrationProgress: number;
  isCalibrated: boolean;
  isMonitoring: boolean;
  isFullscreen: boolean;
  trustScore: number;
  exitCount: number;
  activeAlert: {
    type: string;
    message: string;
    timestamp: number;
    penalty: number;
    score: number;
  } | null;
  audioLevel: number;
  fps: number;
  violationCounts: Record<string, number>;
  violationHistory: ProctoringViolationPayload[];
  bufferedEventsCount: number;
}

export interface ProctoringActions {
  startEngine: () => Promise<boolean>;
  stopEngine: () => void;
  startCalibration: () => Promise<any>;
  enterFullscreen: () => Promise<boolean>;
  dismissAlert: () => void;
  flushBufferedEvents: () => Promise<void>;
}

export interface ProctoringEngineHookReturn {
  videoRef: React.RefObject<HTMLVideoElement | null>;
  canvasRef: React.RefObject<HTMLCanvasElement | null>;
  status: ProctoringStatus;
  actions: ProctoringActions;
}

export function useProctoringEngine(config?: ProctoringEngineConfig): ProctoringEngineHookReturn;

