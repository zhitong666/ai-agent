import os
from typing import ClassVar

from arq.connections import RedisSettings

from app.tasks import analyze_job_task, on_shutdown, on_startup


class WorkerSettings:
    functions: ClassVar[list] = [analyze_job_task]
    on_startup = on_startup
    on_shutdown = on_shutdown

    redis_settings = RedisSettings.from_dsn(
        os.getenv("REDIS_URL", "redis://localhost:6379/0")
    )

    max_jobs = 10
    job_timeout = 120
    keep_result = 3600