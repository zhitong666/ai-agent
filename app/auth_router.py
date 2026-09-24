import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.auth_dependencies import get_current_user, require_roles
from app.auth_models import (
    LoginRequest,
    RegisterRequest,
    TokenPayload,
    TokenResponse,
    UserPublic,
)
from app.auth_security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.config import get_settings
from app.quota import QuotaStatus
from app.redis_rate_limiter import RedisRateLimiter

router = APIRouter(prefix="/auth", tags=["auth"])


def get_user_repository(request: Request):
    return request.app.state.user_repository


def get_quota_service(request: Request):
    return request.app.state.quota_service


def get_rate_limiter(request: Request):
    return getattr(request.app.state, "rate_limiter", None)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")

    if forwarded:
        return forwarded.split(",", 1)[0].strip()

    return request.client.host if request.client else "unknown"


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    payload: RegisterRequest,
    user_repo=Depends(get_user_repository),
):
    if not get_settings().allow_registration:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="registration is disabled",
        )

    try:
        user = await user_repo.create_user(
            payload.username,
            hash_password(payload.password),
            payload.tenant_id,
            payload.roles,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    token = create_access_token(
        subject=user["username"],
        roles=user["roles"],
        tenant_id=user["tenant_id"],
    )

    return TokenResponse(access_token=token)


@router.post("/guest", response_model=TokenResponse)
async def guest_session(
    request: Request,
    rate_limiter: RedisRateLimiter | None = Depends(get_rate_limiter),
):
    if rate_limiter is not None:
        allowed = await rate_limiter.allow(
            f"guest:issue:{_client_ip(request)}",
            limit=10,
            window_seconds=3600,
        )

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="guest session requests are rate limited",
            )

    token = create_access_token(
        subject=f"guest:{uuid.uuid4()}",
        roles=["guest"],
        tenant_id="guest",
        expires_delta=timedelta(hours=24),
    )

    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    payload: LoginRequest,
    user_repo=Depends(get_user_repository),
):
    rate_limiter = get_rate_limiter(request)

    if rate_limiter is not None:
        allowed = await rate_limiter.allow(
            f"auth:login:{_client_ip(request)}",
            limit=10,
            window_seconds=60,
        )

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="too many login attempts",
            )

    user = await user_repo.get_by_username(payload.username)

    if user is None or not verify_password(
        payload.password,
        user["password_hash"],
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid username or password",
        )

    token = create_access_token(
        subject=user["username"],
        roles=user["roles"],
        tenant_id=user["tenant_id"],
    )

    return TokenResponse(access_token=token)


@router.get("/quota", response_model=QuotaStatus)
async def quota(
    user=Depends(get_current_user),
    quota_service=Depends(get_quota_service),
):
    return await quota_service.status(user.sub, user.roles)


@router.get("/me", response_model=UserPublic)
async def me(user: TokenPayload = Depends(get_current_user)):
    return UserPublic(
        username=user.sub,
        roles=user.roles,
        tenant_id=user.tenant_id,
    )


@router.get("/admin/users", response_model=list[UserPublic])
async def admin_list_users(
    user: TokenPayload = Depends(require_roles("admin")),
    user_repo=Depends(get_user_repository),
):
    users = await user_repo.list_users()

    return [
        UserPublic(
            username=item["username"],
            roles=item["roles"],
            tenant_id=item["tenant_id"],
        )
        for item in users
    ]