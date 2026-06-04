import shutil
import tempfile
import unittest
from pathlib import Path

from config.settings import Config
from utils.logger import setup_logger


class TestLogger(unittest.TestCase):
    def setUp(self):
        self.tempdir = Path(tempfile.mkdtemp())
        self.orig_logs = Config.LOGS_DIR
        Config.LOGS_DIR = self.tempdir

    def tearDown(self):
        Config.LOGS_DIR = self.orig_logs
        shutil.rmtree(self.tempdir)

    def test_setup_logger_is_idempotent(self):
        logger1 = setup_logger("test_logger")
        handler_count = len(logger1.handlers)

        logger2 = setup_logger("test_logger")
        self.assertEqual(len(logger2.handlers), handler_count)
        self.assertIs(logger1, logger2)
