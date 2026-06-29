import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.logging import setup_logging


class TestLogger(unittest.TestCase):
    def setUp(self):
        self.tempdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    @patch("app.core.logging.get_settings")
    def test_setup_logger_is_idempotent(self, mock_settings):
        mock_settings.return_value.log_level = "INFO"
        mock_settings.return_value.logs_dir = self.tempdir

        logger1 = setup_logging("test_logger")
        handler_count = len(logger1.handlers)

        logger2 = setup_logging("test_logger")
        self.assertEqual(len(logger2.handlers), handler_count)
        self.assertIs(logger1, logger2)
