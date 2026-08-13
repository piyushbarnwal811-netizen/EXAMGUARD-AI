from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


def normalize_roll_no(value: str) -> str:
    return value.strip().upper()


class StudentCreate(BaseModel):
    roll_no: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=120)
    email: EmailStr

    @field_validator("roll_no")
    @classmethod
    def validate_roll_no(cls, value: str) -> str:
        return normalize_roll_no(value)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name is required.")
        return value


class StudentCsvRow(StudentCreate):
    row_number: int


class StudentLogin(BaseModel):
    roll_no: str = Field(..., min_length=1, max_length=50)
    pin: str = Field(..., min_length=6, max_length=6, pattern=r"^[A-Za-z0-9]{6}$")

    @field_validator("roll_no")
    @classmethod
    def validate_roll_no(cls, value: str) -> str:
        return normalize_roll_no(value)

    @field_validator("pin")
    @classmethod
    def validate_pin(cls, value: str) -> str:
        return value.strip().upper()


class AdminLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    student_id: int | None = None
    session_id: int | None = None
    roll_no: str | None = None


class StudentOut(BaseModel):
    id: int
    roll_no: str
    name: str
    email: EmailStr
    is_pin_used: bool

    model_config = ConfigDict(from_attributes=True)


class CsvUploadResult(BaseModel):
    filename: str
    inserted: int
    updated: int
    total_students: int


class InviteFailure(BaseModel):
    email: EmailStr
    error: str


class StudentImportResult(BaseModel):
    filename: str
    inserted: int
    updated: int
    total_students: int
    invites_sent: int
    invites_failed: int
    failed_invites: list[InviteFailure] = Field(default_factory=list)


class InviteBatchResult(BaseModel):
    total_students: int
    invites_sent: int
    invites_failed: int
    failed_invites: list[InviteFailure] = Field(default_factory=list)


class InviteTokenVerify(BaseModel):
    token: str = Field(..., min_length=24, max_length=255)
    pin: str = Field(..., min_length=6, max_length=6, pattern=r"^[A-Za-z0-9]{6}$")

    @field_validator("pin")
    @classmethod
    def validate_pin(cls, value: str) -> str:
        return value.strip().upper()


class PinRecord(BaseModel):
    roll_no: str
    name: str
    email: EmailStr
    pin: str


class PinGenerationResult(BaseModel):
    total_students: int
    pins: list[PinRecord]
