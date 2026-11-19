import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from main import clean_phone, clean_email, clean, check_facts, process, extract_locally


class FakeExtractor:
    """Predictable fake LLM so tests never need an API key or internet."""
    def __init__(self, mapping):
        self.mapping = mapping

    def __call__(self, entry):
        return self.mapping[entry]


class ProjectTests(unittest.TestCase):
    def test_local_extraction_reads_explicit_registration_fields(self):
        extracted = extract_locally(
            "Name: priya k, ph 98400 12345, email PRIYA.K@gmail.com, 2nd yr CSE"
        )
        self.assertEqual(extracted["name"], "priya k")
        self.assertEqual(extracted["phone"], "9840012345")
        self.assertEqual(extracted["email"], "PRIYA.K@gmail.com")
        self.assertEqual(extracted["year"], "2")
        self.assertEqual(extracted["branch"], "CSE")

    def test_local_extraction_handles_unlabeled_name_and_final_year(self):
        extracted = extract_locally(
            "Arun Kumar | 9876543210 | arun.kumar@yahoo.com | III year ECE"
        )
        self.assertEqual(extracted["name"], "Arun Kumar")
        self.assertEqual(extracted["year"], "3")
        self.assertEqual(extracted["branch"], "ECE")

    def test_phone_cleaning(self):
        self.assertEqual(clean_phone("+91 98400-12345"), "9840012345")
        self.assertEqual(clean_phone("09876543210"), "9876543210")

    def test_email_lowercase_only(self):
        self.assertEqual(clean_email("PRIYA.K@gmail.com"), "priya.k@gmail.com")
        self.assertEqual(clean_email("missing@gmail"), "missing@gmail")

    def test_fact_check_rejects_invented_phone(self):
        bad = {"name": "A", "phone": "9999999999", "email": None,
               "year": 1, "branch": "CSE"}
        self.assertIn("phone_not_found_in_original_entry",
                      check_facts("A phone 9840012345", bad))

    def test_duplicate_after_cleaning(self):
        records = [
            {"id": "A1", "entry": "Asha 9840012345 asha@example.com"},
            {"id": "A2", "entry": "Asha +91 98400 12345 asha@example.com"},
        ]
        mapping = {
            records[0]["entry"]: {"name": "Asha", "phone": "9840012345",
                "email": "asha@example.com", "year": 2, "branch": "CSE"},
            records[1]["entry"]: {"name": "Asha", "phone": "9840012345",
                "email": "asha@example.com", "year": 2, "branch": "CSE"},
        }
        clean_rows, problem_rows = process(records, FakeExtractor(mapping))
        self.assertEqual(len(clean_rows), 1)
        self.assertEqual(problem_rows[0]["status"], "duplicate")
        self.assertEqual(problem_rows[0]["duplicate_of"], "A1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
