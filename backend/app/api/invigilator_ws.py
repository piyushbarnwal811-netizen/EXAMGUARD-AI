"""
ExamGuard AI - Live Invigilator Cockpit WebSocket & Real-Time Hub
Module 1: 1:50 Monitoring Grid, Micro-Stream Polling & Live Interventions
"""

from __future__ import annotations
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Set

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ws", tags=["invigilator_realtime"])
rest_router = APIRouter(prefix="/v1/invigilator", tags=["invigilator_cockpit"])

# ---------------------------------------------------------------------------
# IN-MEMORY REAL-TIME HUBS
# ---------------------------------------------------------------------------

class ExamSessionState:
    def __init__(self, session_id: str, candidate_id: str, roll_no: str, name: str):
        self.session_id = session_id
        self.candidate_id = candidate_id
        self.roll_no = roll_no
        self.name = name
        self.trust_score: float = 100.0
        self.latest_violation: str | None = None
        self.thumbnail_base64: str | None = None
        self.is_frozen: bool = False
        self.freeze_reason: str | None = None
        self.is_terminated: bool = False
        self.last_heartbeat: datetime = datetime.now(timezone.utc)
        self.candidate_socket: WebSocket | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "sessionId": self.session_id,
            "candidateId": self.candidate_id,
            "rollNo": self.roll_no,
            "name": self.name,
            "trustScore": self.trust_score,
            "latestViolation": self.latest_violation,
            "thumbnailBase64": self.thumbnail_base64,
            "isFrozen": self.is_frozen,
            "freezeReason": self.freeze_reason,
            "isTerminated": self.is_terminated,
            "lastHeartbeat": self.last_heartbeat.isoformat(),
        }


class RealtimeInvigilatorHub:
    def __init__(self):
        # exam_id -> { session_id -> ExamSessionState }
        self.exam_candidates: Dict[str, Dict[str, ExamSessionState]] = {}
        # exam_id -> set of invigilator WebSockets
        self.invigilator_sockets: Dict[str, Set[WebSocket]] = {}

    def get_or_create_candidate(self, exam_id: str, session_id: str, candidate_id: str, roll_no: str, name: str) -> ExamSessionState:
        if exam_id not in self.exam_candidates:
            self.exam_candidates[exam_id] = {}
        if session_id not in self.exam_candidates[exam_id]:
            self.exam_candidates[exam_id][session_id] = ExamSessionState(session_id, candidate_id, roll_no, name)
        return self.exam_candidates[exam_id][session_id]

    def register_invigilator(self, exam_id: str, ws: WebSocket):
        if exam_id not in self.invigilator_sockets:
            self.invigilator_sockets[exam_id] = set()
        self.invigilator_sockets[exam_id].add(ws)

    def unregister_invigilator(self, exam_id: str, ws: WebSocket):
        if exam_id in self.invigilator_sockets:
            self.invigilator_sockets[exam_id].discard(ws)

    async def broadcast_to_invigilators(self, exam_id: str, message: dict[str, Any]):
        """Dispatches real-time update to all active invigilator cockpit screens for this exam."""
        sockets = list(self.invigilator_sockets.get(exam_id, set()))
        dead_sockets = []
        payload_text = json.dumps(message)

        for ws in sockets:
            try:
                await ws.send_text(payload_text)
            except Exception:
                dead_sockets.append(ws)

        for dead in dead_sockets:
            self.unregister_invigilator(exam_id, dead)

    async def send_to_candidate(self, exam_id: str, session_id: str, message: dict[str, Any]) -> bool:
        """Sends targeted command directly to student's browser socket."""
        state = self.exam_candidates.get(exam_id, {}).get(session_id)
        if state and state.candidate_socket:
            try:
                await state.candidate_socket.send_text(json.dumps(message))
                return True
            except Exception as e:
                logger.warning(f"Failed to deliver command to candidate {session_id}: {e}")
                return False
        return False


hub = RealtimeInvigilatorHub()


# ---------------------------------------------------------------------------
# WEBSOCKET ENDPOINT: Invigilator Cockpit & Candidate Socket
# ---------------------------------------------------------------------------
@router.websocket("/invigilator/{exam_id}")
async def websocket_invigilator_endpoint(
    websocket: WebSocket,
    exam_id: str,
    role: str = Query("invigilator"),
    session_id: str = Query(""),
    candidate_id: str = Query(""),
    roll_no: str = Query(""),
    name: str = Query(""),
):
    await websocket.accept()

    if role == "invigilator":
        # Invigilator connected
        hub.register_invigilator(exam_id, websocket)
        try:
            # Send initial full state of all active candidates in this exam (up to 50)
            existing_candidates = [
                c.to_dict() for c in hub.exam_candidates.get(exam_id, {}).values()
            ]
            await websocket.send_text(json.dumps({
                "type": "INITIAL_MATRIX_STATE",
                "examId": exam_id,
                "candidates": existing_candidates,
            }))

            while True:
                data = await websocket.receive_text()
                msg = json.loads(data)
                event_type = msg.get("type")

                # Handle Intervention Commands from Invigilator Cockpit
                if event_type == "TRIGGER_AUDIO_ALERT":
                    target_session = msg.get("sessionId")
                    await hub.send_to_candidate(exam_id, target_session, {
                        "type": "TRIGGER_AUDIO_ALERT",
                        "sessionId": target_session,
                        "audioBase64": msg.get("audioBase64"),
                        "audioBufferUrl": msg.get("audioBufferUrl"),
                        "message": msg.get("message", "Keep your eyes on the screen."),
                    })

                elif event_type == "TOGGLE_SESSION_FREEZE":
                    target_session = msg.get("sessionId")
                    is_frozen = bool(msg.get("isFrozen", True))
                    reason = msg.get("reason", "Integrity check in progress")

                    cand_state = hub.exam_candidates.get(exam_id, {}).get(target_session)
                    if cand_state:
                        cand_state.is_frozen = is_frozen
                        cand_state.freeze_reason = reason

                    # Send to candidate
                    await hub.send_to_candidate(exam_id, target_session, {
                        "type": "TOGGLE_SESSION_FREEZE",
                        "sessionId": target_session,
                        "isFrozen": is_frozen,
                        "reason": reason,
                    })

                    # Broadcast state update to all other invigilators
                    await hub.broadcast_to_invigilators(exam_id, {
                        "type": "CANDIDATE_FREEZE_UPDATED",
                        "sessionId": target_session,
                        "isFrozen": is_frozen,
                        "reason": reason,
                    })

                elif event_type == "FORCE_TERMINATE":
                    target_session = msg.get("sessionId")
                    reason = msg.get("reason", "Session terminated by invigilator.")

                    cand_state = hub.exam_candidates.get(exam_id, {}).get(target_session)
                    if cand_state:
                        cand_state.is_terminated = True

                    await hub.send_to_candidate(exam_id, target_session, {
                        "type": "FORCE_TERMINATE",
                        "sessionId": target_session,
                        "reason": reason,
                    })

                    await hub.broadcast_to_invigilators(exam_id, {
                        "type": "CANDIDATE_TERMINATED",
                        "sessionId": target_session,
                        "reason": reason,
                    })

        except WebSocketDisconnect:
            hub.unregister_invigilator(exam_id, websocket)
        except Exception as e:
            logger.error(f"Invigilator socket exception: {e}")
            hub.unregister_invigilator(exam_id, websocket)

    elif role == "candidate":
        # Candidate connected
        cand_state = hub.get_or_create_candidate(
            exam_id=exam_id,
            session_id=session_id or f"session_{id(websocket)}",
            candidate_id=candidate_id or f"cand_{id(websocket)}",
            roll_no=roll_no or "N/A",
            name=name or "Candidate",
        )
        cand_state.candidate_socket = websocket

        try:
            while True:
                data = await websocket.receive_text()
                msg = json.loads(data)
                event_type = msg.get("type")

                # Inbound Heartbeat from Candidate (Every 4-5 Seconds)
                if event_type == "CANDIDATE_HEARTBEAT":
                    cand_state.trust_score = float(msg.get("trustScore", cand_state.trust_score))
                    cand_state.latest_violation = msg.get("latestViolation")
                    cand_state.thumbnail_base64 = msg.get("thumbnailBase64") or cand_state.thumbnail_base64
                    cand_state.last_heartbeat = datetime.now(timezone.utc)

                    # Relay live snapshot & telemetry to all connected invigilators
                    await hub.broadcast_to_invigilators(exam_id, {
                        "type": "CANDIDATE_HEARTBEAT",
                        "candidate": cand_state.to_dict(),
                    })

        except WebSocketDisconnect:
            if cand_state.candidate_socket == websocket:
                cand_state.candidate_socket = None
        except Exception as e:
            logger.error(f"Candidate socket exception: {e}")
            if cand_state.candidate_socket == websocket:
                cand_state.candidate_socket = None


# ---------------------------------------------------------------------------
# REST INTERVENTION FALLBACK ENDPOINTS
# ---------------------------------------------------------------------------
class InterveneRequest(BaseModel):
    action: str  # "WARN", "FREEZE", "UNFREEZE", "TERMINATE"
    sessionId: str
    message: str | None = None
    reason: str | None = None
    audioBase64: str | None = None


@rest_router.get("/{exam_id}/matrix")
async def get_live_matrix_snapshot(exam_id: str):
    """Returns the current 1:50 active candidate matrix state."""
    candidates = [
        c.to_dict() for c in hub.exam_candidates.get(exam_id, {}).values()
    ]
    return {
        "examId": exam_id,
        "totalActive": len(candidates),
        "candidates": candidates,
    }


@rest_router.post("/{exam_id}/intervene")
async def execute_live_intervention(exam_id: str, payload: InterveneRequest):
    """REST endpoint to trigger live voice warning, screen freeze, or disqualification."""
    action = payload.action.upper()
    session_id = payload.sessionId

    if action == "WARN":
        await hub.send_to_candidate(exam_id, session_id, {
            "type": "TRIGGER_AUDIO_ALERT",
            "sessionId": session_id,
            "audioBase64": payload.audioBase64,
            "message": payload.message or "Warning: Maintain test integrity.",
        })
        return {"status": "dispatched", "action": "WARN"}

    elif action in {"FREEZE", "UNFREEZE"}:
        is_frozen = (action == "FREEZE")
        reason = payload.reason or "Investigating suspected irregularity."
        cand_state = hub.exam_candidates.get(exam_id, {}).get(session_id)
        if cand_state:
            cand_state.is_frozen = is_frozen
            cand_state.freeze_reason = reason

        await hub.send_to_candidate(exam_id, session_id, {
            "type": "TOGGLE_SESSION_FREEZE",
            "sessionId": session_id,
            "isFrozen": is_frozen,
            "reason": reason,
        })
        await hub.broadcast_to_invigilators(exam_id, {
            "type": "CANDIDATE_FREEZE_UPDATED",
            "sessionId": session_id,
            "isFrozen": is_frozen,
            "reason": reason,
        })
        return {"status": "success", "isFrozen": is_frozen}

    elif action == "TERMINATE":
        reason = payload.reason or "Disqualified by Invigilator."
        cand_state = hub.exam_candidates.get(exam_id, {}).get(session_id)
        if cand_state:
            cand_state.is_terminated = True

        await hub.send_to_candidate(exam_id, session_id, {
            "type": "FORCE_TERMINATE",
            "sessionId": session_id,
            "reason": reason,
        })
        await hub.broadcast_to_invigilators(exam_id, {
            "type": "CANDIDATE_TERMINATED",
            "sessionId": session_id,
            "reason": reason,
        })
        return {"status": "terminated"}

    raise HTTPException(status_code=400, detail=f"Unsupported action: {action}")

