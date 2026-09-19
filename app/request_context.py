import contextvars
import uuid

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id",
    default="-",
)


def new_request_id(value: str | None = None) -> str:
    request_id = value or uuid.uuid4().hex
    request_id_var.set(request_id)
    return request_id


def get_request_id() -> str:
    return request_id_var.get()