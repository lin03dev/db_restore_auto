import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

import yaml

from app.domain.backup import BackupManager


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


class TestBackupManager(unittest.TestCase):
    def setUp(self):
        self.tempdir = Path(tempfile.mkdtemp())
        self.config_dir = self.tempdir / "config"
        self.config_dir.mkdir()
        self.dumps_dir = self.tempdir / "dumps"
        self.dumps_dir.mkdir()
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

    def test_backup_summary_for_missing_dump(self):
        manager = BackupManager(
            config_path=str(self.config_file),
            settings=self.settings,
        )
        summary = manager.get_backup_summary()

        self.assertIn("AG", summary)
        self.assertFalse(summary["AG"]["exists"])
        self.assertIsNone(summary["AG"]["age_days"])
        self.assertTrue(summary["AG"]["needs_refresh"])

    def test_needs_backup_with_recent_dump(self):
        dump_path = self.dumps_dir / "AG_Prod.dump"
        dump_path.write_bytes(b"dummy data")
        one_day_ago = time.time() - 86400
        os.utime(dump_path, (one_day_ago, one_day_ago))

        manager = BackupManager(
            config_path=str(self.config_file),
            settings=self.settings,
        )
        self.assertFalse(manager.needs_backup(dump_path))

    def test_backup_summary_for_existing_dump(self):
        dump_path = self.dumps_dir / "AG_Prod.dump"
        dump_path.write_bytes(b"dummy data")
        one_day_ago = time.time() - 86400
        os.utime(dump_path, (one_day_ago, one_day_ago))

        manager = BackupManager(
            config_path=str(self.config_file),
            settings=self.settings,
        )
        summary = manager.get_backup_summary()

        self.assertTrue(summary["AG"]["exists"])
        self.assertEqual(summary["AG"]["age_days"], 1)
        self.assertEqual(summary["AG"]["size_mb"], manager.get_file_size_mb(dump_path))
