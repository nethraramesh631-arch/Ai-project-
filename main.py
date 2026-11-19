"""Event Registration Cleaner - console application."""
import argparse
import csv
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / "registrations.csv"
PROMPT_FILE = BASE_DIR / "prompts" / "system_prompt.txt"
CLEAN_FILE = BASE_DIR / "clean_list.csv"
PROBLEMS_FILE = BASE_DIR / "problems.csv"
SUMMARY_FILE = BASE_DIR / "summary.txt"

ALLOWED_BRANCHES = {"CSE", "IT", "AIDS", "ECE", "EEE", "MECH", "CIVIL"}
FIELDS = ("name", "phone", "email", "year", "branch")


def read_entry(row):
    """Read one CSV row and return its id and original unmodified entry."""
    return {
        "id": (row.get("id") or "").strip(),
        "entry": (row.get("entry") or "").strip()
    }


def load_system_prompt():
    return PROMPT_FILE.read_text(encoding="utf-8")


def llm_extract(entry, client=None):
    """
    Ask the LLM to COPY details from one entry.
    It must not clean or correct anything.
    OPENAI_API_KEY is read from the environment, never stored in this file.
    """
    if client is None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "OpenAI package missing. Run: pip install -r requirements.txt"
            ) from exc
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Add your API key as an environment variable."
            )
        client = OpenAI()

    response = client.responses.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        instructions=load_system_prompt(),
        input="Extract the fields from this registration entry. Return JSON only:\n" + entry,
    )
    data = json.loads(response.output_text)
    if not isinstance(data, dict):
        raise ValueError("LLM response was not a JSON object.")
    return {field: data.get(field) for field in FIELDS}


def digits_only(value):
    return re.sub(r"\D", "", str(value or ""))


def phone_candidates_from_entry(entry):
    """Find digit groups that look like phone numbers, allowing spaces/dashes/+."""
    candidates = re.findall(r"(?<!\w)\+?\d(?:[\d\s-]{7,}\d)", entry)
    return [digits_only(candidate) for candidate in candidates if digits_only(candidate)]


def extract_locally(entry):
    """Extract only explicit values from an entry without using a remote service."""
    email_match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", entry, re.I)
    phone_matches = re.finditer(r"(?<!\w)\+?\d(?:[\d\s-]{7,}\d)", entry)
    phone_match = next(phone_matches, None)

    name_match = re.search(
        r"(?:^|[,;|]\s*)name\s*[:=]\s*([^,;|]+)", entry, re.I
    )
    if name_match:
        name = name_match.group(1).strip()
    else:
        end_positions = [
            match.start() for match in (phone_match, email_match) if match
        ]
        name = entry[:min(end_positions)] if end_positions else ""
        name = re.split(r"[,;|]", name, maxsplit=1)[0].strip()
        name = re.sub(r"^name\s*[:=]\s*", "", name, flags=re.I).strip()

    year_match = re.search(
        r"\b(final|first|second|third|fourth|[1-4](?:st|nd|rd|th)?|iv|iii|ii|i)"
        r"\s*(?:year|yr)\b",
        entry,
        re.I,
    )
    branch_match = re.search(
        r"\b(" + "|".join(sorted(ALLOWED_BRANCHES, key=len, reverse=True))
        + r"|other)\b",
        entry,
        re.I,
    )
    phone = digits_only(phone_match.group(0)) if phone_match else None

    return {
        "name": name or None,
        "phone": phone,
        "email": email_match.group(0) if email_match else None,
        "year": str(clean_year(year_match.group(1))) if year_match else None,
        "branch": branch_match.group(1).upper() if branch_match else None,
    }


def check_facts(entry, extracted):
    """
    Reject phone/email values not literally supported by the original entry.
    This prevents the model from inventing or silently correcting contact details.
    """
    problems = []
    phone = extracted.get("phone")
    email = extracted.get("email")

    if phone is not None:
        phone_digits = digits_only(phone)
        candidates = phone_candidates_from_entry(entry)
        if not phone_digits or not any(phone_digits in candidate for candidate in candidates):
            problems.append("phone_not_found_in_original_entry")
    if email is not None:
        if not isinstance(email, str) or email not in entry:
            problems.append("email_not_found_exactly_in_original_entry")
    return problems


def clean_phone(phone):
    """Remove formatting only; never add, remove, or change an actual phone digit."""
    if phone is None:
        return None
    cleaned = digits_only(phone)
    if cleaned.startswith("91") and len(cleaned) == 12:
        cleaned = cleaned[2:]
    elif cleaned.startswith("0") and len(cleaned) == 11:
        cleaned = cleaned[1:]
    return cleaned


def clean_email(email):
    """Lowercase an email; do not complete or repair it."""
    if email is None:
        return None
    return str(email).strip().lower()


def clean_name(name):
    if name is None:
        return None
    return " ".join(str(name).split()).title()


def clean_year(year):
    if year is None or year == "":
        return None
    if isinstance(year, int):
        return year
    value = str(year).strip().lower()
    roman = {"i": 1, "ii": 2, "iii": 3, "iv": 4}
    ordinal = {
        "first": 1, "second": 2, "third": 3, "fourth": 4,
        "1st": 1, "2nd": 2, "3rd": 3, "4th": 4,
    }
    if value in roman:
        return roman[value]
    if value in ordinal:
        return ordinal[value]
    match = re.search(r"\b([1-4])\b", value)
    if match:
        return int(match.group(1))
    if "final" in value:
        return 4
    return None


def clean_branch(branch):
    if branch is None:
        return None
    value = re.sub(r"[^A-Za-z]", "", str(branch)).upper()
    return value if value in ALLOWED_BRANCHES else "other"


def is_valid(record):
    """Return (valid_boolean, list_of_reasons) for a cleaned record."""
    reasons = []
    if not record.get("name"):
        reasons.append("missing_name")
    phone = record.get("phone")
    if not phone:
        reasons.append("missing_phone")
    elif not (len(phone) == 10 and phone[0] in "6789" and phone.isdigit()):
        reasons.append("invalid_phone")
    email = record.get("email")
    if not email:
        reasons.append("missing_email")
    elif (
        not isinstance(email, str)
        or " " in email
        or email.count("@") != 1
        or "." not in email.split("@")[-1]
    ):
        reasons.append("invalid_email")
    year = record.get("year")
    if year not in (1, 2, 3, 4):
        reasons.append("missing_or_invalid_year")
    if record.get("branch") in (None, "", "other"):
        reasons.append("missing_or_other_branch")
    return len(reasons) == 0, reasons


def clean(extracted):
    """Apply only the deterministic cleaning rules specified in the project."""
    return {
        "name": clean_name(extracted.get("name")),
        "phone": clean_phone(extracted.get("phone")),
        "email": clean_email(extracted.get("email")),
        "year": clean_year(extracted.get("year")),
        "branch": clean_branch(extracted.get("branch")),
    }


def process(records, extractor):
    """
    Process rows in order. The first valid occurrence owns a phone/email.
    extractor(entry) must return a dictionary of copied fields.
    """
    clean_rows = []
    problem_rows = []
    seen_phones = {}
    seen_emails = {}

    for row in records:
        item = read_entry(row)
        reasons = []
        try:
            extracted = extractor(item["entry"])
            if not isinstance(extracted, dict):
                raise ValueError("Extractor did not return a dictionary.")
            fact_problems = check_facts(item["entry"], extracted)
            reasons.extend(fact_problems)
            cleaned = clean(extracted)

            # A fact-check failure makes the relevant extracted contact unusable.
            if "phone_not_found_in_original_entry" in fact_problems:
                cleaned["phone"] = None
            if "email_not_found_exactly_in_original_entry" in fact_problems:
                cleaned["email"] = None

            _, validation_reasons = is_valid(cleaned)
            reasons.extend(validation_reasons)

            duplicate_of = None
            phone = cleaned.get("phone")
            email = cleaned.get("email")
            if phone and phone in seen_phones:
                duplicate_of = seen_phones[phone]
            elif email and email in seen_emails:
                duplicate_of = seen_emails[email]

            if duplicate_of:
                status = "duplicate"
                reasons.append("duplicate_of_" + duplicate_of)
            elif reasons:
                status = "needs_fix"
            else:
                status = "valid"

            result = {
                "id": item["id"], **cleaned,
                "status": status, "duplicate_of": duplicate_of,
                "reasons": "; ".join(dict.fromkeys(reasons)),
                "original_entry": item["entry"],
            }

            # Remember the first occurrence after cleaning, even if another
            # field is invalid. Duplicate checking is based on cleaned contact
            # details, not on whether the whole registration is valid.
            if not duplicate_of:
                if phone:
                    seen_phones.setdefault(phone, item["id"])
                if email:
                    seen_emails.setdefault(email, item["id"])

            if status == "valid":
                clean_rows.append({"id": item["id"], **cleaned})
            else:
                problem_rows.append(result)

        except Exception as exc:
            # A failed/malformed LLM reply must not stop the whole batch.
            problem_rows.append({
                "id": item["id"], "name": None, "phone": None, "email": None,
                "year": None, "branch": None, "status": "needs_fix",
                "duplicate_of": None,
                "reasons": "extraction_error: " + str(exc),
                "original_entry": item["entry"],
            })
    return clean_rows, problem_rows


def write_reports(clean_rows, problem_rows, total_count):
    """Write the two CSV reports and a text summary."""
    clean_fields = ["id", "name", "phone", "email", "year", "branch"]
    problem_fields = [
        "id", "name", "phone", "email", "year", "branch", "status",
        "duplicate_of", "reasons", "original_entry"
    ]
    with CLEAN_FILE.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=clean_fields)
        writer.writeheader()
        writer.writerows(clean_rows)

    with PROBLEMS_FILE.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=problem_fields)
        writer.writeheader()
        writer.writerows(problem_rows)

    statuses = Counter(row["status"] for row in problem_rows)
    statuses["valid"] = len(clean_rows)
    branch_year_counts = Counter(
        (row["branch"], row["year"]) for row in clean_rows
    )
    lines = [
        "EVENT REGISTRATION CLEANER - SUMMARY",
        "=" * 40,
        f"Total entries: {total_count}",
        f"Valid: {len(clean_rows)}",
        f"Needs fixing: {statuses.get('needs_fix', 0)}",
        f"Duplicates: {statuses.get('duplicate', 0)}",
        "",
        "VALID REGISTRATIONS BY BRANCH AND YEAR",
        "-" * 40,
    ]
    if branch_year_counts:
        for (branch, year), count in sorted(branch_year_counts.items()):
            lines.append(f"{branch}, Year {year}: {count}")
    else:
        lines.append("No valid registrations.")
    lines += [
        "",
        "Human checkpoint: The event team must contact everyone listed in",
        "problems.csv and confirm/correct details. The program never guesses",
        "or silently changes a phone number or email address."
    ]
    SUMMARY_FILE.write_text("\n".join(lines), encoding="utf-8")


def read_csv(path):
    try:
        with Path(path).open("r", newline="", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)
            if not {"id", "entry"}.issubset(reader.fieldnames or []):
                raise ValueError("CSV must contain columns named id and entry.")
            return list(reader)
    except FileNotFoundError:
        raise FileNotFoundError(f"Input file not found: {path}")


def main():
    parser = argparse.ArgumentParser(description="Clean event registrations.")
    parser.add_argument("--input", default=str(INPUT_FILE), help="Input CSV path")
    args = parser.parse_args()

    try:
        records = read_csv(args.input)
        if not records:
            print("The CSV has no registration rows.")
            return
        start = time.perf_counter()
        clean_rows, problem_rows = process(records, llm_extract)
        write_reports(clean_rows, problem_rows, len(records))
        elapsed = time.perf_counter() - start
        print("\nProcessing completed.")
        print(f"Entries read: {len(records)}")
        print(f"Valid: {len(clean_rows)}")
        print(f"Needs fixing or duplicate: {len(problem_rows)}")
        print(f"Time taken: {elapsed:.2f} seconds")
        print(f"Created: {CLEAN_FILE.name}, {PROBLEMS_FILE.name}, {SUMMARY_FILE.name}")
        print("Please have the event team review problems.csv.")
    except Exception as exc:
        print("Project error:", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
