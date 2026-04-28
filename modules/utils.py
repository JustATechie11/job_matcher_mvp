import json
import os
import re
from datetime import datetime


HISTORY_FILE = "data/search_history.json"


def normalize_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip().lower()


def clean_url(url: str) -> str:
    if not url:
        return ""
    return str(url).strip()


def make_job_key(job: dict) -> str:
    title = normalize_text(job.get("job_role", ""))
    company = normalize_text(job.get("company", ""))
    link = clean_url(job.get("job_link", ""))

    if link:
        return f"link::{link}"

    return f"title_company::{title}::{company}"


def is_duplicate_job(job: dict, existing_jobs: list[dict]) -> bool:
    new_key = make_job_key(job)

    for existing in existing_jobs:
        if new_key == make_job_key(existing):
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