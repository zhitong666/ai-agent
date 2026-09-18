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

router = APIRouter(prefix="/auth", tags=["auth"])


def get_user_repository(request: Request):
    return request.app.state.user_repository


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    request: RegisterRequest,
    user_repo=Depends(get_user_repository),
):
    try:
        user = await user_repo.create_user(
            request.username,
            hash_password(request.password),
            request.tenant_id,
            request.roles,
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


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    user_repo=Depends(get_user_repository),
):
    user = await user_repo.get_by_username(request.username)

    if user is None or not verify_password(
        request.password,
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