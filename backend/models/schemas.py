from pydantic import BaseModel, EmailStr


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


class SecretFinding(BaseModel):
    file: str
    line: int
    type: str
    masked_value: str
    severity: str


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


class AlertResponse(BaseModel):
    id: int
    trap_id: str
    ip: str
    location: str
    lat: float
    lng: float
    isp: str
    browser: str
    os: str
    device: str
    timestamp: str
    source_type: str | None = None
    context: str | None = None
