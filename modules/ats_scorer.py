import re
from rapidfuzz import fuzz


ROLE_SKILL_PROFILES = {
    "platform": {
        "core": {
            "kubernetes": ["kubernetes", "k8s", "eks", "aks", "gke", "openshift"],
            "cloud": ["aws", "azure", "gcp", "cloud"],
            "iac": ["terraform", "bicep", "cloudformation", "arm template", "infrastructure as code", "iac"],
            "cicd": ["ci/cd", "cicd", "github actions", "jenkins", "azure devops", "gitlab ci"],
            "containers": ["docker", "container", "containerized"],
            "automation": ["automation", "python", "bash", "powershell", "scripting"],
            "observability": ["prometheus", "grafana", "elk", "splunk", "opentelemetry", "logging", "monitoring"],
            "platform_engineering": ["platform engineering", "platform services", "developer platform", "internal developer platform", "self-service"],
        },
        "preferred": {
            "security": ["security", "secure coding", "cloud security", "least privilege", "iam"],
            "api": ["api", "rest", "restful", "microservices", "platform api"],
            "reliability": ["reliability", "scalability", "sre", "incident", "slis", "slos"],
            "leadership": ["leadership", "mentor", "cross-functional", "stakeholder"],
            "tools": ["harness", "jira", "git", "yaml", "json"],
        },
    },
    "data": {
        "core": {
            "sql": ["sql", "joins", "cte", "window functions", "subqueries"],
            "python": ["python", "pandas", "numpy"],
            "bi": ["power bi", "tableau", "dashboard", "reporting"],
            "analytics": ["data analysis", "analytics", "kpi", "trend analysis"],
            "database": ["mysql", "postgresql", "snowflake", "sql server", "bigquery"],
        },
        "preferred": {
            "cloud": ["aws", "azure", "gcp", "redshift", "athena"],
            "etl": ["etl", "data pipeline", "data modeling"],
            "healthcare": ["healthcare", "claims", "ehr", "hipaa", "hedis", "cms"],
        },
    },
}


EQUIVALENCE_GROUPS = [
    ["eks", "aks", "gke", "kubernetes", "k8s"],
    ["terraform", "bicep", "cloudformation", "arm template"],
    ["github actions", "jenkins", "azure devops", "gitlab ci"],
    ["prometheus", "grafana", "elk", "splunk", "opentelemetry"],
    ["aws", "azure", "gcp"],
]


def normalize(text: str) -> str:
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[^a-z0-9+#./\-\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def contains_any(text: str, keywords: list[str]) -> bool:
    text = normalize(text)
    return any(normalize(keyword) in text for keyword in keywords)


def detect_role_profile(target_role: str, job_title: str, job_description: str) -> str:
    combined = normalize(f"{target_role} {job_title} {job_description}")

    platform_terms = [
        "platform engineer", "devops", "sre", "infrastructure",
        "cloud engineer", "kubernetes", "terraform", "ci/cd"
    ]

    data_terms = [
        "data analyst", "business intelligence", "bi analyst",
        "healthcare analyst", "financial analyst", "sql", "power bi"
    ]

    platform_score = sum(1 for term in platform_terms if term in combined)
    data_score = sum(1 for term in data_terms if term in combined)

    if platform_score >= data_score:
        return "platform"

    return "data"


def skill_group_match(resume_text: str, jd_text: str, skill_groups: dict) -> tuple[int, int, list, list, list]:
    matched = []
    missing = []
    partial = []

    total_groups = len(skill_groups)
    score_units = 0

    for group_name, keywords in skill_groups.items():
        jd_needs_group = contains_any(jd_text, keywords)
        resume_has_group = contains_any(resume_text, keywords)

        if not jd_needs_group:
            continue

        if resume_has_group:
            matched.append(group_name)
            score_units += 1
        else:
            # Check equivalent/transferable match
            equivalent_found = False
            for eq_group in EQUIVALENCE_GROUPS:
                if any(k in keywords for k in eq_group):
                    jd_has_eq = contains_any(jd_text, eq_group)
                    resume_has_eq = contains_any(resume_text, eq_group)

                    if jd_has_eq and resume_has_eq:
                        equivalent_found = True
                        break

            if equivalent_found:
                partial.append(group_name)
                score_units += 0.6
            else:
                missing.append(group_name)

    applicable_groups = len(matched) + len(partial) + len(missing)

    return score_units, applicable_groups, matched, partial, missing


def calculate_ats_score(resume_text: str, job: dict, target_role: str) -> dict:
    resume_text = normalize(resume_text)

    jd_text = normalize(" ".join([
        job.get("job_role", ""),
        job.get("company", ""),
        job.get("description", ""),
        job.get("experience_required", ""),
    ]))

    job_title = job.get("job_role", "")

    role_profile_name = detect_role_profile(target_role, job_title, jd_text)
    profile = ROLE_SKILL_PROFILES[role_profile_name]

    core_score_units, core_total, core_matched, core_partial, core_missing = skill_group_match(
        resume_text,
        jd_text,
        profile["core"]
    )

    preferred_score_units, preferred_total, preferred_matched, preferred_partial, preferred_missing = skill_group_match(
        resume_text,
        jd_text,
        profile["preferred"]
    )

    core_score = 0
    if core_total:
        core_score = (core_score_units / core_total) * 55

    preferred_score = 0
    if preferred_total:
        preferred_score = (preferred_score_units / preferred_total) * 20

    title_score = fuzz.token_set_ratio(normalize(target_role), normalize(job_title)) * 0.15

    description_score = fuzz.token_set_ratio(resume_text[:4000], jd_text[:4000]) * 0.10

    total_score = round(min(core_score + preferred_score + title_score + description_score, 100), 2)

    if total_score >= 85:
        verdict = "Strong Match"
    elif total_score >= 75:
        verdict = "Good Match"
    elif total_score >= 65:
        verdict = "Average Match"
    else:
        verdict = "Weak Match"

    matched_keywords = core_matched + preferred_matched
    partial_keywords = core_partial + preferred_partial
    missing_keywords = core_missing + preferred_missing

    return {
        "ats_score": total_score,
        "verdict": verdict,
        "role_profile": role_profile_name,
        "matched_keywords": matched_keywords,
        "partial_matches": partial_keywords,
        "missing_keywords": missing_keywords,
        "match_reason": build_match_reason(
            total_score,
            matched_keywords,
            partial_keywords,
            missing_keywords
        )
    }


def build_match_reason(score: float, matched: list, partial: list, missing: list) -> str:
    matched_text = ", ".join(matched[:6]) if matched else "limited direct match"
    partial_text = ", ".join(partial[:5]) if partial else "none"
    missing_text = ", ".join(missing[:6]) if missing else "no major missing areas"

    return (
        f"Recruiter-style score based on role-specific skill groups. "
        f"Matched: {matched_text}. "
        f"Transferable/partial: {partial_text}. "
        f"Missing: {missing_text}."
    )