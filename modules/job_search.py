import os
import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests
from dotenv import load_dotenv

load_dotenv()

SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY", "").strip()
MIN_SALARY = int(os.getenv("MIN_SALARY", "70000"))
MAX_POSTED_DAYS = int(os.getenv("MAX_POSTED_DAYS", "9"))
GOOGLE_JOBS_PAGES = int(os.getenv("GOOGLE_JOBS_PAGES", "3"))
DIRECT_SEARCH_PAGES = int(os.getenv("DIRECT_SEARCH_PAGES", "2"))
MAX_DIRECT_QUERIES = int(os.getenv("MAX_DIRECT_QUERIES", "90"))


ALLOWED_ATS_DOMAINS = {
    "Greenhouse": ["greenhouse.io"],
    "Workday": ["workdayjobs.com", "myworkdayjobs.com", "myworkdaysite.com"],
    "iCIMS": ["icims.com"],
    "SuccessFactors": ["successfactors.com", "successfactors.eu", "sapsf.com"],
    "Ashby": ["ashbyhq.com"],
    "SmartRecruiters": ["smartrecruiters.com"],
    "Oracle": ["oraclecloud.com", "oracle.com"],
    "Rippling": ["rippling-ats.com", "rippling.com"],
    "ADP": ["workforcenow.adp.com", "adp.com"],
    "Ulippo": ["ulippo.com"],
    "Jobs Lovers": ["jobslovers.com"],
}

DIRECT_JOB_DOMAINS = sorted({domain for domains in ALLOWED_ATS_DOMAINS.values() for domain in domains})

BLOCKED_JOB_BOARD_DOMAINS = [
    "linkedin.com",
    "indeed.com",
    "glassdoor.com",
    "monster.com",
    "ziprecruiter.com",
    "careerbuilder.com",
    "dice.com",
    "wellfound.com",
    "angellist.com",
    "builtin.com",
    "simplyhired.com",
    "jooble.org",
    "talent.com",
    "theladders.com",
    "snagajob.com",
    "upwork.com",
    "freelancer.com",
    "remoteok.com",
    "weworkremotely.com",
]

COMPANY_CAREER_PATH_HINTS = [
    "/career",
    "/careers",
    "/jobs",
    "/job/",
    "/open-positions",
    "/openings",
    "/opportunities",
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
    "staffing",
    "recruiting",
    "recruitment",
    "search firm",
    "talent acquisition",
    "workforce solutions",
    "manpower",
    "aerotek",
    "beacon hill",
    "consulting services",
    "employment agency",
    "staff augmentation",
    "headhunter",
    "recruiter",
    "contract to hire",
    "lockheed martin",
    "lockheedmartin",
    "lockheedmartinjobs",
    "northrop grumman",
    "raytheon",
    "rtx",
    "general dynamics",
    "gdit",
    "booz allen",
    "leidos",
    "saic",
    "caci",
    "l3harris",
    "bae systems",
    "dod",
    "department of defense",
    "security clearance",
    "secret clearance",
    "top secret",
    "ts/sci",
    "polygraph",
    "federal contractor",
    "government contractor",
    "usajobs",
    ".gov",
]


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


def has_us_location_signal(location: str) -> bool:
    text = normalize(location)
    if not text:
        return False

    if any(signal in text for signal in ["united states", "usa", "u.s.", "remote"]):
        return True

    state_codes = {
        "al", "ak", "az", "ar", "ca", "co", "ct", "dc", "de", "fl", "ga", "hi",
        "ia", "id", "il", "in", "ks", "ky", "la", "ma", "md", "me", "mi", "mn",
        "mo", "ms", "mt", "nc", "nd", "ne", "nh", "nj", "nm", "nv", "ny", "oh",
        "ok", "or", "pa", "ri", "sc", "sd", "tn", "tx", "ut", "va", "vt", "wa",
        "wi", "wv", "wy",
    }
    tokens = set(re.findall(r"\b[a-z]{2}\b", text))
    return bool(tokens & state_codes)


def get_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def normalize_url(url: str) -> str:
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


def is_company_career_page(link: str) -> bool:
    parsed = urlparse(link)
    domain = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.lower()

    if not domain or any(blocked in domain for blocked in BLOCKED_JOB_BOARD_DOMAINS):
        return False

    if any(domain == allowed or domain.endswith(f".{allowed}") for allowed in DIRECT_JOB_DOMAINS):
        return False

    return any(hint in path for hint in COMPANY_CAREER_PATH_HINTS)


def is_allowed_job_link(link: str) -> bool:
    if not link or not str(link).startswith("http"):
        return False

    domain = get_domain(link)
    if any(blocked in domain for blocked in BLOCKED_JOB_BOARD_DOMAINS):
        return False

    if any(domain == allowed or domain.endswith(f".{allowed}") for allowed in DIRECT_JOB_DOMAINS):
        return True

    return is_company_career_page(link)


def detect_platform_from_url(link: str) -> str:
    link = link.lower()
    domain = get_domain(link)

    for platform, domains in ALLOWED_ATS_DOMAINS.items():
        if any(domain == allowed or domain.endswith(f".{allowed}") or allowed in link for allowed in domains):
            return platform

    if is_company_career_page(link):
        return "Company Career Page"

    return "Blocked or Unknown"


def is_blocked_job(job: dict) -> bool:
    combined = normalize(
        f"{job.get('company', '')} {job.get('platform', '')} "
        f"{job.get('job_link', '')} {job.get('description', '')}"
    )
    return any(blocked in combined for blocked in BLOCKED_COMPANIES_OR_PLATFORMS)


def title_matches_role(title: str, target_role: str, minimum_overlap: float = 0.45) -> bool:
    ignored = {"and", "the", "for", "with", "remote", "usa", "united", "states"}
    title_words = {
        word for word in re.findall(r"[a-z0-9+#]+", normalize(title))
        if len(word) > 2 and word not in ignored
    }
    role_words = {
        word for word in re.findall(r"[a-z0-9+#]+", normalize(target_role))
        if len(word) > 2 and word not in ignored
    }

    if not role_words:
        return True

    return len(title_words & role_words) / len(role_words) >= minimum_overlap


def dedupe_jobs(jobs: list[dict]) -> list[dict]:
    seen = set()
    unique = []
    generic_companies = {
        "company via workday",
        "company via greenhouse",
        "company via ashby",
        "company not clearly detected",
    }

    for job in jobs:
        link = normalize_url(job.get("job_link", ""))
        title = normalize(job.get("job_role", ""))
        company = normalize(job.get("company", ""))
        link_key = f"link::{link}" if link else ""
        title_company_key = f"title_company::{title}::{company}"

        has_specific_company = company and company not in generic_companies

        if link_key in seen or (has_specific_company and title_company_key in seen):
            continue

        if link_key:
            seen.add(link_key)
        if has_specific_company:
            seen.add(title_company_key)
        unique.append(job)

    return unique


def parse_salary_and_check(salary_str: str, min_salary: int = MIN_SALARY) -> bool:
    if not salary_str or salary_str.lower() in {"not mentioned", "not clearly mentioned"}:
        return True

    text = salary_str.lower().replace("k", "000")
    numbers = []

    for match in re.finditer(r"\b\d+(?:,\d{3})*\b", text):
        try:
            num = int(match.group().replace(",", ""))
        except ValueError:
            continue

        if num > 1000:
            numbers.append(num)

    if not numbers:
        return True

    return max(numbers) >= min_salary


def check_recent_date(date_str: str, max_days: int = MAX_POSTED_DAYS) -> bool:
    if not date_str or date_str.lower() in {"not mentioned", "not clearly mentioned"}:
        return True

    text = date_str.lower()
    day_match = re.search(r"(\d+)\s+days?", text)
    if day_match:
        return int(day_match.group(1)) <= max_days

    if re.search(r"(\d+)\s+hours?", text):
        return True

    if any(term in text for term in ["today", "just posted", "yesterday"]):
        return True

    if "week" in text and not re.search(r"1\s+week|a\s+week", text):
        return False

    if "month" in text or "year" in text:
        return False

    return True


def build_role_variations(job_role: str) -> list[str]:
    role = normalize(job_role)
    variations = [job_role]

    if any(term in role for term in ["ai/ml", "machine learning", " ml ", "artificial intelligence"]):
        variations.extend(
            [
                "Machine Learning Engineer",
                "AI Engineer",
                "ML Engineer",
                "Artificial Intelligence Engineer",
                "Applied AI Engineer",
                "Generative AI Engineer",
                "MLOps Engineer",
                "AI Software Engineer",
            ]
        )
    elif "data analyst" in role:
        variations.extend(["Business Intelligence Analyst", "BI Analyst", "Analytics Analyst"])
    elif "software" in role or "developer" in role:
        variations.extend(["Software Engineer", "Backend Engineer", "Full Stack Engineer"])

    unique = []
    seen = set()
    for variation in variations:
        key = normalize(variation)
        if key not in seen:
            seen.add(key)
            unique.append(variation)
    return unique


def build_direct_search_queries(job_role: str) -> list[str]:
    queries = []
    platform_domains = {
        "greenhouse": ["boards.greenhouse.io", "job-boards.greenhouse.io", "greenhouse.io"],
        "workday": ["myworkdayjobs.com", "myworkdaysite.com", "workdayjobs.com"],
        "icims": ["icims.com"],
        "successfactors": ["successfactors.com", "successfactors.eu", "sapsf.com"],
        "ashby": ["ashbyhq.com"],
        "smartrecruiters": ["smartrecruiters.com"],
        "oracle": ["oraclecloud.com"],
        "rippling": ["rippling-ats.com", "rippling.com"],
        "adp": ["workforcenow.adp.com"],
        "ulippo": ["ulippo.com"],
        "jobslovers": ["jobslovers.com"],
    }

    for role in build_role_variations(job_role):
        for domains in platform_domains.values():
            domain_query = " OR ".join([f"site:{domain}" for domain in domains])
            queries.extend(
                [
                    f'({domain_query}) "{role}" "United States" apply',
                    f'({domain_query}) "{role}" "Remote" apply',
                    f'({domain_query}) "{role}" "posted" apply',
                    f'({domain_query}) "{role}" "$70,000" apply',
                ]
            )

        queries.extend(
            [
                f'"{role}" "United States" "$70,000" intitle:careers apply -linkedin -indeed -ziprecruiter -glassdoor',
                f'"{role}" "remote" "United States" intitle:jobs apply -linkedin -indeed -glassdoor -ziprecruiter',
                f'"{role}" "United States" "apply" "careers" -linkedin -indeed -glassdoor -ziprecruiter',
                f'"{role}" "Remote" "apply" "careers" -linkedin -indeed -glassdoor -ziprecruiter',
            ]
        )

    unique_queries = []
    seen = set()
    for query in queries:
        key = normalize(query)
        if key not in seen:
            seen.add(key)
            unique_queries.append(query)

    return unique_queries[:MAX_DIRECT_QUERIES]


def build_google_jobs_queries(job_role: str, location: str) -> list[str]:
    queries = []

    for role in build_role_variations(job_role):
        queries.extend(
            [
                f'{role} $70,000+ jobs in United States',
                f'{role} "{location}" "$70,000" careers apply',
                f'{role} remote United States "$70,000" careers apply',
            ]
        )

    return queries


def search_google_jobs_serpapi(job_role: str, location: str, limit: int = 50) -> list[dict]:
    if not SERPAPI_API_KEY:
        print("SERPAPI_API_KEY is missing.")
        return []

    results = []

    for query in build_google_jobs_queries(job_role, location):
        if len(results) >= limit:
            break

        params = {
            "engine": "google_jobs",
            "q": query,
            "location": "United States",
            "api_key": SERPAPI_API_KEY,
            "hl": "en",
            "gl": "us",
            "chips": "date_posted:week",
        }

        page_params = params.copy()

        for _ in range(GOOGLE_JOBS_PAGES):
            if len(results) >= limit:
                break

            try:
                response = requests.get("https://serpapi.com/search.json", params=page_params, timeout=25)
                print("SerpAPI Google Jobs Status:", response.status_code)
                response.raise_for_status()
                data = response.json()

                if "error" in data:
                    print("SerpAPI Error:", data["error"])
                    break

                jobs = data.get("jobs_results", [])
                print("Google Jobs found:", len(jobs), "for query:", query)

                for item in jobs:
                    posted_date = item.get("detected_extensions", {}).get("posted_at", "Not clearly mentioned")
                    if not check_recent_date(posted_date):
                        continue

                    salary = item.get("detected_extensions", {}).get("salary", "Not mentioned")
                    if not parse_salary_and_check(salary):
                        continue

                    title = item.get("title", "")
                    if not title_matches_role(title, job_role):
                        continue

                    location_text = item.get("location", "")
                    if not has_us_location_signal(location_text):
                        continue

                    for option in item.get("apply_options", [])[:8]:
                        job_link = option.get("link", "")
                        if not is_allowed_job_link(job_link):
                            continue

                        job = {
                            "job_role": title,
                            "company": item.get("company_name", ""),
                            "platform": detect_platform_from_url(job_link),
                            "job_link": job_link,
                            "salary": salary,
                            "location": location_text,
                            "posted_date": posted_date,
                            "description": item.get("description", ""),
                            "source": "serpapi_google_jobs",
                        }

                        if not is_blocked_job(job):
                            results.append(job)

                        if len(results) >= limit:
                            break

                next_page_token = data.get("serpapi_pagination", {}).get("next_page_token")
                if not next_page_token:
                    break
                page_params = params.copy()
                page_params["next_page_token"] = next_page_token

            except Exception as e:
                print(f"Google Jobs SerpAPI search failed: {e}")
                break

    return dedupe_jobs(results)


def search_direct_career_pages_serpapi(job_role: str, location: str, limit: int = 250) -> list[dict]:
    if not SERPAPI_API_KEY:
        return []

    queries = build_direct_search_queries(job_role)

    results = []

    for query in queries:
        if len(results) >= limit:
            break

        params = {
            "engine": "google",
            "q": query,
            "api_key": SERPAPI_API_KEY,
            "hl": "en",
            "gl": "us",
            "tbs": f"qdr:d{MAX_POSTED_DAYS}",
            "num": 20,
        }

        for start in range(0, DIRECT_SEARCH_PAGES * 10, 10):
            if len(results) >= limit:
                break

            params["start"] = start

            try:
                response = requests.get("https://serpapi.com/search.json", params=params, timeout=25)
                print("SerpAPI Direct Search Status:", response.status_code)
                response.raise_for_status()
                data = response.json()

                if "error" in data:
                    print("SerpAPI Direct Error:", data["error"])
                    break

                organic_results = data.get("organic_results", [])
                print("Direct career pages found:", len(organic_results), "for query:", query)

                for item in organic_results:
                    link = item.get("link", "")
                    title = item.get("title", "")
                    snippet = item.get("snippet", "")

                    if not is_allowed_job_link(link):
                        continue

                    job_title = clean_job_title_from_search(title, job_role)
                    if not title_matches_role(job_title, job_role, minimum_overlap=0.34):
                        continue

                    job = {
                        "job_role": job_title,
                        "company": extract_company_from_link_or_title(link, title),
                        "platform": detect_platform_from_url(link),
                        "job_link": link,
                        "salary": "Not disclosed; search filtered toward $70,000+",
                        "location": location,
                        "posted_date": f"Past {MAX_POSTED_DAYS} Days",
                        "description": snippet,
                        "source": "serpapi_direct_career_search",
                    }

                    if not is_blocked_job(job):
                        results.append(job)

                    if len(results) >= limit:
                        break

                if len(organic_results) < 10:
                    break

            except Exception as e:
                print(f"Direct career page search failed: {e}")
                break

    return dedupe_jobs(results)


def clean_job_title_from_search(title: str, fallback_role: str) -> str:
    cleaned = title or fallback_role

    for sep in [" - ", " | ", " at ", " @ ", " – "]:
        if sep in cleaned:
            cleaned = cleaned.split(sep)[0].strip()
            break

    if len(cleaned) < 3:
        cleaned = fallback_role

    return cleaned


def extract_company_from_link_or_title(link: str, title: str) -> str:
    text = f"{link} {title}".lower()

    if "greenhouse" in text:
        for marker in ["boards.greenhouse.io/", "job-boards.greenhouse.io/"]:
            if marker in link:
                return link.split(marker)[1].split("/")[0].replace("-", " ").title()
        return "Company via Greenhouse"

    if "ashbyhq" in text:
        try:
            return link.split("ashbyhq.com/")[1].split("/")[0].replace("-", " ").title()
        except Exception:
            return "Company via Ashby"

    if "workdayjobs" in text or "myworkdayjobs" in text:
        return "Company via Workday"

    domain = get_domain(link)
    if domain:
        return domain.split(".")[0].replace("-", " ").title()

    return "Company not clearly detected"


def search_jobs(job_role: str, location: str, limit: int = 50) -> list[dict]:
    all_jobs = []
    location = "United States"
    candidate_limit = max(limit * 6, 300)

    google_jobs = search_google_jobs_serpapi(
        job_role=job_role,
        location=location,
        limit=max(limit * 3, 150),
    )
    all_jobs.extend(google_jobs)

    direct_jobs = search_direct_career_pages_serpapi(
        job_role=job_role,
        location=location,
        limit=candidate_limit,
    )
    all_jobs.extend(direct_jobs)

    all_jobs = dedupe_jobs(all_jobs)
    print("Total raw unique jobs:", len(all_jobs))

    return all_jobs[:candidate_limit]
