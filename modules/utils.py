import json
import os
import re
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


HISTORY_FILE = "data/search_history.json"


def normalize_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip().lower()


def is_blocked_seniority_title(title: str) -> bool:
    title = normalize_text(title)
    return bool(re.search(r"\b(lead|staff)\b", title))


def _extract_experience_candidates(text: str) -> list[int]:
    text = normalize_text(text)
    if not text:
        return []
    text = re.sub(r"[’']", "", text)

    patterns = [
        r"\b(\d{1,2})\s*(?:\+|plus)?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:professional\s+)?experience\b",
        r"\b(?:minimum|min\.?|at\s+least|over|more\s+than)\s+(\d{1,2})\s*(?:\+|plus)?\s*(?:years?|yrs?)\b",
        r"\b(\d{1,2})\s*(?:\+|plus)?\s*(?:years?|yrs?)\s+(?:in|with|building|developing|working)\b",
        r"\b(\d{1,2})\s*-\s*\d{1,2}\s*(?:years?|yrs?)\b",
    ]

    candidates = []
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            years = int(match.group(1))
            if 0 <= years <= 30:
                candidates.append(years)

    return candidates


def extract_resume_experience_years(resume_text: str) -> int | None:
    candidates = _extract_experience_candidates(resume_text)
    return max(candidates) if candidates else None


def extract_job_required_experience_years(job_text: str) -> int | None:
    candidates = _extract_experience_candidates(job_text)
    return min(candidates) if candidates else None


def format_experience_years(years: int | None) -> str:
    if years is None:
        return "Not clearly mentioned"
    return str(years)


def job_experience_allowed(required_years: int | None, resume_years: int | None) -> bool:
    if required_years is None or resume_years is None:
        return True
    return required_years <= resume_years


def clean_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(str(url).strip())
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in {"gh_src", "source", "src"}
    ]
    return urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower().removeprefix("www."),
            parsed.path.rstrip("/"),
            "",
            urlencode(query),
            "",
        )
    )


def make_job_key(job: dict) -> str:
    title = normalize_text(job.get("job_role", ""))
    company = normalize_text(job.get("company", ""))
    link = clean_url(job.get("job_link", ""))

    title_company_key = f"title_company::{title}::{company}"

    if link:
        return f"link::{link}::{title_company_key}"

    return title_company_key


def is_duplicate_job(job: dict, existing_jobs: list[dict]) -> bool:
    new_link = clean_url(job.get("job_link", ""))
    new_title = normalize_text(job.get("job_role", ""))
    new_company = normalize_text(job.get("company", ""))
    generic_companies = {
        "company via workday",
        "company via greenhouse",
        "company via ashby",
        "company not clearly detected",
    }

    for existing in existing_jobs:
        existing_link = clean_url(existing.get("job_link", ""))
        existing_title = normalize_text(existing.get("job_role", ""))
        existing_company = normalize_text(existing.get("company", ""))

        if new_link and existing_link and new_link == existing_link:
            return True

        has_specific_company = new_company and existing_company and new_company not in generic_companies
        if has_specific_company and new_title == existing_title and new_company == existing_company:
            return True

    return False


def current_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def create_search_id(first_name: str, last_name: str, job_role: str) -> str:
    name = f"{first_name}_{last_name}".lower().replace(" ", "_")
    role = normalize_text(job_role).replace(" ", "_")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{name}_{role}_{stamp}"


def load_history() -> list[dict]:
    os.makedirs("data", exist_ok=True)

    if not os.path.exists(HISTORY_FILE):
        return []

    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_search_to_history(search_record: dict) -> None:
    os.makedirs("data", exist_ok=True)

    history = load_history()
    history.insert(0, search_record)

    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def update_search_in_history(search_id: str, updated_jobs: list[dict]) -> None:
    history = load_history()

    for record in history:
        if record.get("search_id") == search_id:
            record["jobs"] = updated_jobs
            record["total_jobs"] = len(updated_jobs)
            record["last_updated"] = current_timestamp()
            break

    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
