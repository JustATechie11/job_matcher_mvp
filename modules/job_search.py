import os
import re
import requests
from dotenv import load_dotenv

load_dotenv()

SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY", "").strip()


DIRECT_JOB_DOMAINS = [
    "jobs.lever.co",
    "boards.greenhouse.io",
    "job-boards.greenhouse.io",
    "ashbyhq.com",
    "jobs.ashbyhq.com",
    "workdayjobs.com",
    "myworkdayjobs.com",
    "smartrecruiters.com",
    "jobs.jobvite.com",
    "careers.icims.com",
]


BLOCKED_COMPANIES_OR_PLATFORMS = [
    "apex systems",
    "teksystems",
    "robert half",
    "randstad",
    "kforce",
    "collabera",
    "judge group",
    "insight global",
    "motion recruitment",
    "cybercoders",
]


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


def is_blocked_job(job: dict) -> bool:
    combined = normalize(
        f"{job.get('company', '')} {job.get('platform', '')} {job.get('description', '')}"
    )

    return any(blocked in combined for blocked in BLOCKED_COMPANIES_OR_PLATFORMS)


def dedupe_jobs(jobs: list[dict]) -> list[dict]:
    seen = set()
    unique = []

    for job in jobs:
        link = normalize(job.get("job_link", ""))
        title = normalize(job.get("job_role", ""))
        company = normalize(job.get("company", ""))

        key = link if link else f"{title}|{company}"

        if key in seen:
            continue

        seen.add(key)
        unique.append(job)

    return unique


def search_google_jobs_serpapi(job_role: str, location: str, limit: int = 30) -> list[dict]:
    if not SERPAPI_API_KEY:
        print("SERPAPI_API_KEY is missing.")
        return []

    queries = [
        f'{job_role} jobs in {location} posted last 7 days',
        f'{job_role} {location} careers apply',
        f'{job_role} remote United States careers apply',
    ]

    results = []

    for query in queries:
        if len(results) >= limit:
            break

        params = {
            "engine": "google_jobs",
            "q": query,
            "location": location,
            "api_key": SERPAPI_API_KEY,
            "hl": "en",
        }

        try:
            response = requests.get(
                "https://serpapi.com/search.json",
                params=params,
                timeout=25,
            )

            print("SerpAPI Google Jobs Status:", response.status_code)
            response.raise_for_status()

            data = response.json()

            if "error" in data:
                print("SerpAPI Error:", data["error"])
                continue

            jobs = data.get("jobs_results", [])
            print("Google Jobs found:", len(jobs), "for query:", query)

            for item in jobs:
                apply_options = item.get("apply_options", [])

                if not apply_options:
                    continue

                for option in apply_options[:3]:
                    job_link = option.get("link", "")

                    if not job_link:
                        continue

                    job = {
                        "job_role": item.get("title", ""),
                        "company": item.get("company_name", ""),
                        "experience_required": "Not clearly mentioned",
                        "platform": option.get("title", "Google Jobs / SerpAPI"),
                        "job_link": job_link,
                        "salary": item.get("detected_extensions", {}).get("salary", "Not mentioned"),
                        "location": item.get("location", ""),
                        "posted_date": item.get("detected_extensions", {}).get("posted_at", "Not clearly mentioned"),
                        "description": item.get("description", ""),
                        "source": "serpapi_google_jobs",
                    }

                    if not is_blocked_job(job):
                        results.append(job)

                    if len(results) >= limit:
                        break

        except Exception as e:
            print(f"Google Jobs SerpAPI search failed: {e}")

    return dedupe_jobs(results)


def search_direct_career_pages_serpapi(job_role: str, location: str, limit: int = 40) -> list[dict]:
    """
    Searches Google organic results for direct ATS/company career pages.
    This improves job count while still using verification later.
    """

    if not SERPAPI_API_KEY:
        return []

    domain_query = " OR ".join([f"site:{domain}" for domain in DIRECT_JOB_DOMAINS[:8]])

    queries = [
        f'({domain_query}) "{job_role}" "{location}" apply',
        f'({domain_query}) "{job_role}" "United States" apply',
        f'({domain_query}) "{job_role}" "Remote" apply',
    ]

    results = []

    for query in queries:
        if len(results) >= limit:
            break

        params = {
            "engine": "google",
            "q": query,
            "api_key": SERPAPI_API_KEY,
            "hl": "en",
            "num": 20,
        }

        try:
            response = requests.get(
                "https://serpapi.com/search.json",
                params=params,
                timeout=25,
            )

            print("SerpAPI Direct Search Status:", response.status_code)
            response.raise_for_status()

            data = response.json()

            if "error" in data:
                print("SerpAPI Direct Error:", data["error"])
                continue

            organic_results = data.get("organic_results", [])
            print("Direct career pages found:", len(organic_results), "for query:", query)

            for item in organic_results:
                link = item.get("link", "")
                title = item.get("title", "")
                snippet = item.get("snippet", "")

                if not link:
                    continue

                if not any(domain in link for domain in DIRECT_JOB_DOMAINS):
                    continue

                job = {
                    "job_role": clean_job_title_from_search(title, job_role),
                    "company": extract_company_from_link_or_title(link, title),
                    "experience_required": "Not clearly mentioned",
                    "platform": detect_platform_from_url(link),
                    "job_link": link,
                    "salary": "Not mentioned",
                    "location": location,
                    "posted_date": "Not clearly mentioned",
                    "description": snippet,
                    "source": "serpapi_direct_career_search",
                }

                if not is_blocked_job(job):
                    results.append(job)

                if len(results) >= limit:
                    break

        except Exception as e:
            print(f"Direct career page search failed: {e}")

    return dedupe_jobs(results)


def clean_job_title_from_search(title: str, fallback_role: str) -> str:
    title = title or fallback_role

    separators = [" - ", " | ", " at ", " @ "]

    cleaned = title

    for sep in separators:
        if sep in cleaned:
            cleaned = cleaned.split(sep)[0].strip()
            break

    if len(cleaned) < 3:
        cleaned = fallback_role

    return cleaned


def extract_company_from_link_or_title(link: str, title: str) -> str:
    text = f"{link} {title}".lower()

    if "lever.co" in text:
        try:
            return link.split("jobs.lever.co/")[1].split("/")[0].replace("-", " ").title()
        except Exception:
            return "Company via Lever"

    if "greenhouse" in text:
        try:
            if "boards.greenhouse.io/" in link:
                return link.split("boards.greenhouse.io/")[1].split("/")[0].replace("-", " ").title()
            if "job-boards.greenhouse.io/" in link:
                return link.split("job-boards.greenhouse.io/")[1].split("/")[0].replace("-", " ").title()
        except Exception:
            return "Company via Greenhouse"

    if "ashbyhq" in text:
        try:
            return link.split("ashbyhq.com/")[1].split("/")[0].replace("-", " ").title()
        except Exception:
            return "Company via Ashby"

    if "workdayjobs" in text or "myworkdayjobs" in text:
        return "Company via Workday"

    return "Company not clearly detected"


def detect_platform_from_url(link: str) -> str:
    link = link.lower()

    if "lever.co" in link:
        return "Lever"
    if "greenhouse" in link:
        return "Greenhouse"
    if "ashbyhq" in link:
        return "Ashby"
    if "workdayjobs" in link or "myworkdayjobs" in link:
        return "Workday"
    if "smartrecruiters" in link:
        return "SmartRecruiters"
    if "jobvite" in link:
        return "Jobvite"
    if "icims" in link:
        return "iCIMS"

    return "Company Career Page"


def get_demo_jobs(job_role: str, location: str) -> list[dict]:
    return [
        {
            "job_role": job_role,
            "company": "Demo Company",
            "experience_required": "2+ years",
            "platform": "Demo",
            "job_link": "https://boards.greenhouse.io/",
            "salary": "Not mentioned",
            "location": location,
            "posted_date": "Demo only",
            "description": f"{job_role} role requiring SQL, Python, analytics, dashboarding, and reporting.",
            "source": "demo",
        }
    ]


def search_jobs(job_role: str, location: str, limit: int = 80) -> list[dict]:
    all_jobs = []

    google_jobs = search_google_jobs_serpapi(
        job_role=job_role,
        location=location,
        limit=limit,
    )
    all_jobs.extend(google_jobs)

    direct_jobs = search_direct_career_pages_serpapi(
        job_role=job_role,
        location=location,
        limit=limit,
    )
    all_jobs.extend(direct_jobs)

    all_jobs = dedupe_jobs(all_jobs)

    if not all_jobs:
        all_jobs = get_demo_jobs(job_role, location)

    print("Total raw unique jobs:", len(all_jobs))

    return all_jobs