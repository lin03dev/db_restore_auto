import unittest

from app.domain.connectivity import classify_connection_error
from app.domain.results import summarize_details


class TestConnectivity(unittest.TestCase):
    def test_classify_ip_restriction(self):
        code, message = classify_connection_error(
            'FATAL: no pg_hba.conf entry for host "1.2.3.4"'
        )
        self.assertEqual(code, "ip_restricted")
        self.assertIn("IP", message)

    def test_classify_unreachable(self):
        code, _ = classify_connection_error("could not connect to server: Connection refused")
        self.assertEqual(code, "unreachable")

    def test_summarize_partial_success(self):
        details = {
            "AG": {"success": True},
            "Telios": {"success": False, "error_code": "ip_restricted"},
        }
        summary = summarize_details(details)
        self.assertTrue(summary["success"])
        self.assertTrue(summary["partial"])
        self.assertEqual(summary["succeeded"], ["AG"])
        self.assertEqual(summary["failed"], ["Telios"])

    def test_summarize_restore_cooldown_skips_are_not_succeeded(self):
        details = {
            "LMS": {"success": True, "skipped": True, "reason": "restore_cooldown"},
            "Telios": {"success": True, "skipped": True, "reason": "restore_cooldown"},
            "AG": {
                "success": False,
                "error_code": "dump_missing",
                "message": "No local dump available.",
            },
        }
        summary = summarize_details(details)
        self.assertTrue(summary["success"])
        self.assertTrue(summary["partial"])
        self.assertEqual(summary["succeeded"], [])
        self.assertEqual(summary["skipped"], ["LMS", "Telios"])
        self.assertEqual(summary["failed"], ["AG"])


    def test_classify_database_in_use(self):
        code, _ = classify_connection_error(
            "DETAIL:  There are 2 other sessions using the database."
        )
        self.assertEqual(code, "database_in_use")


if __name__ == "__main__":
    unittest.main()
