import unittest

from scanner import location_allowed, target_role_allowed


class ScannerSafetyTests(unittest.TestCase):
    def test_india_locations_are_allowed(self):
        for location in (
            "Bengaluru, Karnataka, India",
            "Hyderabad, Telangana, India",
            "Kolkata",
            "Gurugram, Haryana",
            "Chennai",
            "Remote - India",
        ):
            with self.subTest(location=location):
                self.assertTrue(location_allowed(location))

    def test_overseas_locations_are_rejected(self):
        for location in (
            "Singapore, Singapore",
            "Paris, Île-de-France, France",
            "Dallas, TX",
            "Winnipeg, Manitoba, Canada",
            "Serbia",
            "Federal Territory of Kuala Lumpur, Malaysia",
        ):
            with self.subTest(location=location):
                self.assertFalse(location_allowed(location))

    def test_remote_restrictions_are_respected(self):
        self.assertTrue(location_allowed("Remote"))
        self.assertTrue(location_allowed("Remote / Worldwide"))
        self.assertFalse(location_allowed("Remote - United States only"))
        self.assertFalse(location_allowed("APAC"))

    def test_target_transition_titles_are_allowed(self):
        for title in (
            "Data Analyst",
            "Analyst - Data Analytics",
            "Business Intelligence Analyst",
            "MIS Executive",
            "Associate, Reporting and Analytics",
            "Data Analyst - Operations",
        ):
            with self.subTest(title=title):
                self.assertTrue(target_role_allowed(title))

    def test_non_target_titles_are_rejected(self):
        for title in (
            "Customer Support Executive",
            "Software Engineer",
            "Account Executive",
            "Process Associate",
        ):
            with self.subTest(title=title):
                self.assertFalse(target_role_allowed(title))


if __name__ == "__main__":
    unittest.main()
