import re

import requests
from bs4 import BeautifulSoup

from modules.job_search import (
    MAX_POSTED_DAYS,
    detect_platform_from_url,
    has_us_location_signal,
    is_blocked_job,
    is_allowed_job_link,
    parse_salary_and_check,
)


BAD_LINK_KEYWORDS = [
    "expired",
    "no longer available",
    "job not found",
    "position has been filled",
    "this job is closed",
    "this posting has expired",
    "page not found",
    "job has been closed",
    "not accepting applications",
]

APPLY_KEYWORDS = [
    "apply",
    "apply now",
    "submit application",
    "apply for this job",
    "start application",
]

US_LOCATION_SIGNALS = [
    "united states",
    "remote - us",
    "remote us",
    "remote, us",
    "remote (us",
    "u.s.",
    "usa",
]


def extract_salary_text(page_text: str) -> str:
    salary_patterns = [
        r"\$\s?\d{2,3}(?:,\d{3})?(?:\s?-\s?\$\s?\d{2,3}(?:,\d{3})?)?",
        r"\$\s?\d{2,3}\s?k(?:\s?-\s?\$?\s?\d{2,3}\s?k)?",
    ]

    matches = []
    for pattern in salary_patterns:
        matches.extend(re.findall(pattern, page_text, flags=re.IGNORECASE))

    return ", ".join(matches[:3]) if matches else ""


def has_recent_signal(page_text: str, max_days: int = MAX_POSTED_DAYS) -> bool:
    text = page_text.lower()

    if any(term in text for term in ["posted today", "just posted", "posted yesterday"]):
        return True

    for match in re.finditer(r"posted\s+(\d+)\s+days?\s+ago", text):
        if int(match.group(1)) <= max_days:
            return True

    return False


def has_context_us_signal(job_context: dict | None) -> bool:
    if not job_context:
        return False

    if has_us_location_signal(str(job_context.get("location", ""))):
        return True

    source = str(job_context.get("source", "")).lower()
    return source == "serpapi_direct_career_search"


def can_search_verify(job_context: dict | None) -> bool:
    if not job_context:
        return False

    source = str(job_context.get("source", "")).lower()
    return source in {"serpapi_direct_career_search", "serpapi_google_jobs"}


def build_search_verified_result(url: str, reason: str, job_context: dict | None = None) -> dict:
    description = str((job_context or {}).get("description", ""))
    return {
        "is_valid": True,
        "reason": reason,
        "final_url": url,
        "platform": detect_platform_from_url(url),
        "page_text": description[:12000],
        "salary_text": "",
        "recent_signal": True,
    }


def verify_job_link(url: str, job_context: dict | None = None, timeout: int = 12) -> dict:
    if not url or not url.startswith("http"):
        return {
            "is_valid": False,
            "reason": "Invalid URL format",
            "final_url": url,
        }

    if not is_allowed_job_link(url):
        return {
            "is_valid": False,
            "reason": "Blocked job board or unsupported ATS",
            "final_url": url,
        }

    try:
        response = requests.get(
            url,
            timeout=timeout,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
                )
            },
            allow_redirects=True,
        )

        final_url = response.url
        if not is_allowed_job_link(final_url):
            return {
                "is_valid": False,
                "reason": "Redirected to blocked job board or unsupported ATS",
                "final_url": final_url,
            }

        if response.status_code in {401, 403, 408, 409, 425, 429} and can_search_verify(job_context):
            return build_search_verified_result(
                final_url,
                f"Search-verified approved source; page returned HTTP {response.status_code}",
                job_context,
            )

        if response.status_code >= 400:
            return {
                "is_valid": False,
                "reason": f"HTTP error {response.status_code}",
                "final_url": final_url,
            }

        html = response.text.lower()
        for bad_word in BAD_LINK_KEYWORDS:
            if bad_word in html:
                return {
                    "is_valid": False,
                    "reason": f"Inactive page: {bad_word}",
                    "final_url": final_url,
                }

        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        page_text = soup.get_text(" ", strip=True)
        page_text_lower = page_text.lower()
        has_apply_signal = any(keyword in page_text_lower for keyword in APPLY_KEYWORDS)
        has_us_signal = any(signal in page_text_lower for signal in US_LOCATION_SIGNALS)
        has_us_signal = has_us_signal or has_context_us_signal(job_context)
        platform = detect_platform_from_url(final_url)
        has_trusted_ats_signal = platform != "Company Career Page" and len(page_text) > 250

        if is_blocked_job({**(job_context or {}), "job_link": final_url, "description": page_text[:6000]}):
            return {
                "is_valid": False,
                "reason": "Blocked staffing, government, or defense-contractor result",
                "final_url": final_url,
            }

        if not has_apply_signal and not has_trusted_ats_signal and can_search_verify(job_context):
            return build_search_verified_result(
                final_url,
                "Search-verified approved source; apply text not visible to scraper",
                job_context,
            )

        if not has_apply_signal and not has_trusted_ats_signal:
            return {
                "is_valid": False,
                "reason": "No apply signal",
                "final_url": final_url,
            }

        if not has_us_signal and can_search_verify(job_context):
            return build_search_verified_result(
                final_url,
                "Search-verified approved source; USA signal came from search context",
                job_context,
            )

        if not has_us_signal:
            return {
                "is_valid": False,
                "reason": "No clear USA location signal",
                "final_url": final_url,
            }

        salary_text = extract_salary_text(page_text)
        if salary_text and not parse_salary_and_check(salary_text):
            return {
                "is_valid": False,
                "reason": "Salary appears below $70,000",
                "final_url": final_url,
            }

        return {
            "is_valid": True,
            "reason": "Verified approved source with USA signal",
            "final_url": final_url,
            "platform": platform,
            "page_text": page_text[:12000],
            "salary_text": salary_text,
            "recent_signal": has_recent_signal(page_text),
        }

    except Exception as e:
        if can_search_verify(job_context):
            return build_search_verified_result(
                url,
                f"Search-verified approved source; scraper could not fetch page: {e}",
                job_context,
            )

        return {
            "is_valid": False,
            "reason": str(e),
            "final_url": url,
        }
