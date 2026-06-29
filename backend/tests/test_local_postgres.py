import unittest

from app.domain.local_postgres import resolve_local_db_config


class FakeSettings:
    local_db_host = "localhost"
    local_db_port = 5432
    local_db_user = "postgres"
    local_db_password = ""


class TestLocalPostgresConfig(unittest.TestCase):
    def test_yaml_password_used_when_env_empty(self):
        yaml_config = {
            "local_postgres": {
                "host": "localhost",
                "port": 5432,
                "username": "postgres",
                "password": "postgres",
            }
        }
        local = resolve_local_db_config(FakeSettings(), yaml_config)
        self.assertEqual(local["password"], "postgres")

    def test_env_password_takes_precedence(self):
        settings = FakeSettings()
        settings.local_db_password = "from-env"
        yaml_config = {"local_postgres": {"password": "from-yaml"}}
        local = resolve_local_db_config(settings, yaml_config)
        self.assertEqual(local["password"], "from-env")

    def test_yaml_password_used_when_env_placeholder(self):
        settings = FakeSettings()
        settings.local_db_password = "your_local_password"
        yaml_config = {"local_postgres": {"password": "postgres"}}
        local = resolve_local_db_config(settings, yaml_config)
        self.assertEqual(local["password"], "postgres")


if __name__ == "__main__":
    unittest.main()
