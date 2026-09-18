from typing import ClassVar

from arq.connections import RedisSettings

from app.config import get_settings
from app.tasks import analyze_job_task, on_shutdown, on_startup


class WorkerSettings:
    functions: ClassVar[list] = [analyze_job_task]
    on_startup = on_startup
    on_shutdown = on_shutdown

    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)

    max_jobs = 10
    job_timeout = 120
    keep_result = 3600