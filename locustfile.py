import os

from dotenv import load_dotenv
from locust import HttpUser, task

load_dotenv()


class HelloWorldUser(HttpUser):
    host = os.getenv("BACKEND_BASE_URL", "http://localhost:8000")

    @task
    def hello_world(self):
        self.client.get("/api/v1/adapters")
