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
