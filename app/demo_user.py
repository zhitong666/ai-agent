from app.auth_security import hash_password
from app.config import get_settings


async def ensure_demo_user(user_repository) -> dict | None:
    """Create the fixed demo account when it does not exist yet."""
    settings = get_settings()
    username = settings.demo_username

    existing = await user_repository.get_by_username(username)

    if existing is not None:
        return existing

    return await user_repository.create_user(
        username,
        hash_password(settings.demo_password),
        "default",
        ["user", "admin"],
    )
