from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

ALLOWED_TRACKING_EVENTS = {
    "BLOCKED_KEY",
    "CAMERA_ERROR",
    "CAMERA_PERMISSION_DENIED",
    "CAMERA_PERMISSION_REQUESTED",
    "CAMERA_STARTED",
    "CAMERA_STOPPED",
    "CAMERA_TRACK_ENDED",
    "CAMERA_UNAVAILABLE",
    "EXAM_END",
    "EXAM_START",
    "FOCUS_LOST",
    "FOCUS_RETURNED",
    "FULLSCREEN_DENIED",
    "FULLSCREEN_ENTER",
    "FULLSCREEN_EXIT",
    "FULLSCREEN_RESUME_FAILED",
    "FACE_MISSING",
    "IP_MISMATCH",
    "LOCKDOWN_START",
    "LOCKDOWN_STOP",
    "LOCATION",
    "LOCATION_PERMISSION_DENIED",
    "LOCATION_PERMISSION_REQUESTED",
    "LOCATION_UNAVAILABLE",
    "LOOKING_AWAY",
    "MOBILE_DEVICE_BLOCKED",
    "MOBILE_DEVICE_DETECTED",
    "MULTIPLE_FACES",
    "PAGE_HIDE",
    "TAB_SWITCH",
    "VISIBILITY_HIDDEN",
    "VISIBILITY_VISIBLE",
    "WINDOW_BLUR",
    "WINDOW_FOCUS",
}


class QuestionOut(BaseModel):
    id: int
    question: str
    options: list[str]


class AnswerSubmit(BaseModel):
    question_id: int
    selected_option: str = Field(..., min_length=1, max_length=1)

    @field_validator("selected_option")
    @classmethod
    def validate_selected_option(cls, value: str) -> str:
        value = value.strip().upper()
        if value not in {"A", "B", "C", "D"}:
            raise ValueError("selected_option must be one of A, B, C, or D.")
        return value


class ResponseOut(BaseModel):
    question_id: int
    selected_option: str
    submitted_at: datetime
    saved: bool


class TrackingEvent(BaseModel):
    event_type: str
    message: str | None = None
    client_timestamp: datetime | None = None
    latitude: float | None = None
    longitude: float | None = None
    location: str | None = None
    network_isp: str | None = None
    details: dict[str, Any] | None = None

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, value: str) -> str:
        normalized = value.strip().upper().replace("-", "_").replace(" ", "_")
        if normalized not in ALLOWED_TRACKING_EVENTS:
            raise ValueError(
                f"event_type must be one of: {', '.join(sorted(ALLOWED_TRACKING_EVENTS))}"
            )
        return normalized
