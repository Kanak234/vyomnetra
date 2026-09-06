"""Locust Load Test Suite for VYOMNETRA SSA API."""

from locust import HttpUser, task, between

class SSAUser(HttpUser):
    wait_time = between(0.1, 0.5)

    @task(3)
    def test_health(self):
        self.client.get("/health")

    @task(3)
    def test_readiness(self):
        self.client.get("/readiness")

    @task(2)
    def test_satellites(self):
        self.client.get("/satellites?limit=50")

    @task(2)
    def test_conjunctions(self):
        self.client.get("/conjunctions?duration_hours=24")

    @task(1)
    def test_space_weather(self):
        self.client.get("/space-weather")

    @task(1)
    def test_pass_schedule(self):
        self.client.get("/pass-schedule?site_key=hazaribagh&days=1")
