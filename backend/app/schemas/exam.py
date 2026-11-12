from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

ALLOWED_TRACKING_EVENTS = {
    "BACK_NAVIGATION",
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
    "MOBILE_PHONE_DETECTED",
    "MULTIPLE_FACES",
    "PAGE_HIDE",
    "SECONDARY_PHONE_CHEATING",
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
    option_ids: list[str] | None = None


class QuestionCreate(BaseModel):
    question_text: str = Field(..., min_length=3)
    option_a: str = Field(..., min_length=1)
    option_b: str = Field(..., min_length=1)
    option_c: str = Field(..., min_length=1)
    option_d: str = Field(..., min_length=1)
    correct_option: str = Field(..., min_length=1, max_length=1)

    @field_validator("correct_option")
    @classmethod
    def validate_correct_option(cls, value: str) -> str:
        value = value.strip().upper()
        if value not in {"A", "B", "C", "D"}:
            raise ValueError("correct_option must be one of A, B, C, or D.")
        return value


class QuestionAdminOut(BaseModel):
    id: int
    question: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_option: str


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


class BulkQuestionImportResult(BaseModel):
    status: str
    imported_count: int
    skipped_count: int = 0
    errors: list[str] = Field(default_factory=list)


class GenerateAiMcqsRequest(BaseModel):
    topic: str = Field(..., min_length=2, max_length=150)
    count: int = Field(default=5, ge=1, le=30)
    difficulty: str = Field(default="Medium")
    save_immediately: bool = Field(default=False)


class PublishCoachingExamRequest(BaseModel):
    coaching_name: str = Field(..., min_length=2, max_length=120)
    exam_title: str = Field(..., min_length=2, max_length=160)
    duration_minutes: int = Field(default=60, ge=5, le=360)
    instructions: str | None = Field(default=None, max_length=2000)
    total_marks: int | None = Field(default=None)


class PublishCoachingExamResponse(BaseModel):
    status: str
    slug: str
    coaching_name: str
    exam_title: str
    duration_minutes: int
    shareable_url: str
    whatsapp_share_url: str

