import unittest

from fastapi.testclient import TestClient

from app.main import create_app
from app.services.job_service import job_service


class TestJobsApi(unittest.TestCase):
    def setUp(self):
        job_service._jobs.clear()
        self.client = TestClient(create_app())

    def test_start_job_accepts_selected_database(self):
        response = self.client.post(
            "/api/v1/jobs",
            json={"operation": "validate", "databases": ["AG"]},
        )
        self.assertEqual(response.status_code, 202, response.text)
        body = response.json()
        self.assertIn("id", body)
        self.assertEqual(body["operation"], "validate")
        self.assertEqual(body["databases"], ["AG"])

    def test_start_job_accepts_multiple_databases(self):
        response = self.client.post(
            "/api/v1/jobs",
            json={"operation": "validate", "databases": ["AG", "Telios"]},
        )
        self.assertEqual(response.status_code, 202, response.text)
        self.assertEqual(response.json()["databases"], ["AG", "Telios"])

    def test_unknown_database_returns_400(self):
        response = self.client.post(
            "/api/v1/jobs",
            json={"operation": "validate", "databases": ["NotARealDb"]},
        )
        self.assertEqual(response.status_code, 400, response.text)

    def test_empty_databases_means_all(self):
        response = self.client.post(
            "/api/v1/jobs",
            json={"operation": "validate", "databases": []},
        )
        self.assertEqual(response.status_code, 202, response.text)
        self.assertEqual(response.json()["database"], "all")


if __name__ == "__main__":
    unittest.main()
