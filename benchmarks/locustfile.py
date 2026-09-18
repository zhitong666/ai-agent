from locust import HttpUser, between, task


class JobAgentUser(HttpUser):
    wait_time = between(1, 3)

    @task(3)
    def health(self):
        self.client.get("/health")

    @task(2)
    def db_health(self):
        self.client.get("/health/db")

    @task(1)
    def redis_health(self):
        self.client.get("/health/redis")