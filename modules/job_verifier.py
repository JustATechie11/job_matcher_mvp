import requests
from bs4 import BeautifulSoup


BAD_LINK_KEYWORDS = [
    "expired",
    "no longer available",
    "job not found",
    "position has been filled",
    "this job is closed",
    "this posting has expired",
    "page not found",
]


APPLY_KEYWORDS = [
    "apply",
    "apply now",
    "submit",
    "application",
    "apply for this job",
]


def verify_job_link(url: str, timeout: int = 12) -> dict:
    """
    Smarter verification:
    - Accept valid redirect links (LinkedIn, Indeed, company ATS)
    - Avoid over-rejection
    """

    if not url or not url.startswith("http"):
        return {
            "is_valid": False,
            "reason": "Invalid URL format",
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
        status_code = response.status_code

        if status_code >= 400:
            return {
                "is_valid": False,
                "reason": f"HTTP error {status_code}",
                "final_url": final_url,
            }

        html = response.text.lower()

        # Reject clearly dead pages
        for bad_word in BAD_LINK_KEYWORDS:
            if bad_word in html:
                return {
                    "is_valid": False,
                    "reason": f"Inactive page: {bad_word}",
                    "final_url": final_url,
                }

        soup = BeautifulSoup(response.text, "html.parser")
        page_text = soup.get_text(" ", strip=True).lower()

        has_apply_signal = any(keyword in page_text for keyword in APPLY_KEYWORDS)

        # 🔥 KEY FIX:
        # If it's a known job platform, allow even if no clear "apply" text
        trusted_domains = [
            "linkedin.com",
            "indeed.com",
            "greenhouse.io",
            "lever.co",
            "workday",
            "smartrecruiters",
        ]

        if not has_apply_signal:
            if not any(domain in final_url for domain in trusted_domains):
                return {
                    "is_valid": False,
                    "reason": "No apply signal",
                    "final_url": final_url,
                }

        return {
            "is_valid": True,
            "reason": "Verified (trusted or apply detected)",
            "final_url": final_url,
        }

    except Exception as e:
        return {
            "is_valid": False,
            "reason": str(e),
            "final_url": url,
        }