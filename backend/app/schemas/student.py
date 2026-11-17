from pydantic import AliasChoices, BaseModel, ConfigDict, EmailStr, Field, field_validator


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
    model_config = ConfigDict(populate_by_name=True)

    roll_no: str = Field(
        ...,
        min_length=1,
        max_length=50,
        validation_alias=AliasChoices(
            "roll_no",
            "rollNo",
            "rollNumber",
            "student_roll_no",
            "studentRollNo",
        ),
    )
    pin: str = Field(
        ...,
        min_length=6,
        max_length=6,
        pattern=r"^[A-Za-z0-9]{6}$",
        validation_alias=AliasChoices("pin", "student_pin", "studentPin", "studentPIN"),
    )

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
    institute_name: str | None = None
    is_super_admin: bool | None = None


class InstituteCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=180)
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=4, max_length=100)
    contact_person: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=255)


class InstituteOut(BaseModel):
    id: int
    name: str
    code: str
    username: str
    contact_person: str | None = None
    phone: str | None = None
    email: str | None = None
    is_active: bool
    created_at: str | None = None


class InstituteResetPassword(BaseModel):
    new_password: str = Field(..., min_length=4, max_length=100)


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
    token: str = Field(
        ...,
        min_length=24,
        max_length=255,
        validation_alias=AliasChoices("token", "invite", "invite_token", "exam_token"),
    )
    pin: str | None = Field(
        None,
        min_length=6,
        max_length=6,
        pattern=r"^[A-Za-z0-9]{6}$",
        validation_alias=AliasChoices("pin", "student_pin", "studentPin"),
    )

    @field_validator("pin")
    @classmethod
    def validate_pin(cls, value: str | None) -> str | None:
        return value.strip().upper() if value else None


class PinRecord(BaseModel):
    roll_no: str
    name: str
    email: EmailStr
    pin: str


class PinGenerationResult(BaseModel):
    total_students: int
    pins: list[PinRecord]
