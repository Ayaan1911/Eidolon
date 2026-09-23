from pydantic import BaseModel, EmailStr, Field


class EmailCheckRequest(BaseModel):
    email: EmailStr


class BreachData(BaseModel):
    name: str
    date: str
    severity: str
    data_exposed: list[str]


class EmailCheckResponse(BaseModel):
    email: str
    risk_score: int
    total_breaches: int
    breaches: list[BreachData]


class PasswordCheckRequest(BaseModel):
    password: str


class PasswordCheckResponse(BaseModel):
    score: int
    feedback: str
    crack_time_display: str


class PhotoMetadataResponse(BaseModel):
    has_location: bool
    latitude: float | None = None
    longitude: float | None = None
    device: str | None = None
    captured_at: str | None = None


class RepoScanRequest(BaseModel):
    username: str


class TrapStatus(BaseModel):
    trap_url: str
    hit_count: int


class SecretFinding(BaseModel):
    id: str
    file: str
    line: int
    type: str
    masked_value: str
    severity: str
    # Only ever populated for an admin caller - a public scan of someone else's
    # repos must never reveal that a trap exists, let alone its URL.
    trap: TrapStatus | None = None


class RepoFindings(BaseModel):
    repo: str
    findings: list[SecretFinding]


class RepoScanResponse(BaseModel):
    username: str
    repos_scanned: int
    total_findings: int
    results: list[RepoFindings]
    incomplete: bool
    incomplete_reason: str | None = None


class TrapCreateRequest(BaseModel):
    name: str
    source_type: str | None = None
    context: str | None = None


class TrapCreateResponse(BaseModel):
    id: str
    trap_url: str


class FindingTrapRequest(BaseModel):
    """Context the frontend already has from the scan result, used to build a
    trap name/context automatically - no manual naming for a finding-linked trap."""

    repo: str = Field(max_length=200)
    file: str = Field(max_length=500)
    type: str = Field(max_length=100)


class AlertResponse(BaseModel):
    id: int
    trap_id: str
    ip: str
    location: str
    lat: float
    lng: float
    isp: str
    org: str | None = None
    asn: str | None = None
    browser: str
    os: str
    device: str
    referer: str | None = None
    # Set only on hits from a submitted fake login form (password_attempted is None on a page load).
    email: str | None = None
    password_attempted: bool | None = None
    password_length: int | None = None
    timestamp: str
    source_type: str | None = None
    context: str | None = None


class TrapLoginAttempt(BaseModel):
    """What the fake login page reports on submit. The browser sends only the
    password's length - the password itself never leaves the page - and any
    other field (e.g. a stray "password") is ignored, never stored."""

    email: str = Field(default="", max_length=320)
    password_length: int = Field(ge=0, le=1024)


class AdminLoginRequest(BaseModel):
    passphrase: str


class AdminLoginResponse(BaseModel):
    token: str
    expires_at: int


class HoneytokenResponse(BaseModel):
    token: str
    base_url: str
