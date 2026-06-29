import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

from app.domain.restore import RestoreManager


class FakeSettings:
    def __init__(self, tempdir: Path, config_file: Path):
        self.base_dir = tempdir
        self.dumps_dir = tempdir / "dumps"
        self.logs_dir = tempdir / "logs"
        self.databases_config = config_file
        self.backup_max_age_days = 7
        self.restore_cooldown_days = 7
        self.local_db_config = {
            "host": "localhost",
            "port": "5432",
            "username": "postgres",
            "password": "",
        }


class TestRestoreManager(unittest.TestCase):
    def setUp(self):
        self.tempdir = Path(tempfile.mkdtemp())
        self.config_dir = self.tempdir / "config"
        self.config_dir.mkdir()
        self.logs_dir = self.tempdir / "logs"
        self.logs_dir.mkdir()

        self.config_file = self.config_dir / "databases.yaml"
        self.config_file.write_text(
            yaml.safe_dump(
                {
                    "databases": [
                        {
                            "name": "AG",
                            "source_dump": "AG_Prod.dump",
                            "target_db": "AG_Dev",
                            "enabled": True,
                            "source_config": {
                                "connection_string_env": "AG_PROD_CONNECTION",
                                "pg_dump_path": "pg_dump",
                            },
                        }
                    ]
                }
            )
        )
        self.settings = FakeSettings(self.tempdir, self.config_file)

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def test_restore_status_never_restored(self):
        manager = RestoreManager(
            config_path=str(self.config_file),
            settings=self.settings,
        )
        status = manager.get_restore_status()

        self.assertIn("AG_Dev", status)
        self.assertIsNone(status["AG_Dev"]["last_restore"])
        self.assertTrue(status["AG_Dev"]["can_restore"])

    def test_save_tracking_records_restore(self):
        manager = RestoreManager(
            config_path=str(self.config_file),
            settings=self.settings,
        )
        manager.tracking_file = self.tempdir / ".restore_tracking.json"
        manager.save_tracking("AG_Dev")

        status = manager.get_restore_status()
        self.assertIn("AG_Dev", status)
        self.assertIsNotNone(status["AG_Dev"]["last_restore"])
        self.assertEqual(status["AG_Dev"]["days_ago"], 0)
        self.assertFalse(status["AG_Dev"]["can_restore"])
