from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    tenant_id: str = Field(default="default")
    roles: list[str] = Field(default_factory=lambda: ["user"])


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str
    roles: list[str]
    tenant_id: str
    exp: int


class UserPublic(BaseModel):
    username: str
    roles: list[str]
    tenant_id: str