import re
from collections import Counter

from rapidfuzz import fuzz


ROLE_SKILL_PROFILES = {
    "ai_ml": {
        "core": {
            "machine_learning": [
                "machine learning", "ml", "modeling", "predictive modeling", "classification",
                "regression", "recommendation", "ranking",
            ],
            "python": ["python", "pandas", "numpy", "scikit-learn", "sklearn"],
            "ml_frameworks": ["pytorch", "tensorflow", "keras", "xgboost", "lightgbm"],
            "genai_llm": [
                "generative ai", "genai", "llm", "large language model", "openai",
                "langchain", "rag", "prompt engineering",
            ],
            "mlops": [
                "mlops", "model deployment", "model serving", "feature store", "kubeflow",
                "mlflow", "sagemaker", "vertex ai", "azure ml",
            ],
            "data": ["sql", "spark", "databricks", "etl", "data pipeline", "data engineering"],
        },
        "preferred": {
            "cloud": ["aws", "azure", "gcp", "docker", "kubernetes"],
            "api": ["api", "rest", "fastapi", "flask", "microservices"],
            "evaluation": ["model evaluation", "experimentation", "a/b testing", "metrics"],
            "statistics": ["statistics", "probability", "linear algebra", "optimization"],
            "vector_search": ["vector database", "embedding", "pinecone", "weaviate", "faiss", "milvus"],
        },
    },
    "platform": {
        "core": {
            "kubernetes": ["kubernetes", "k8s", "eks", "aks", "gke", "openshift"],
            "cloud": ["aws", "azure", "gcp", "cloud"],
            "iac": ["terraform", "bicep", "cloudformation", "arm template", "infrastructure as code", "iac"],
            "cicd": ["ci/cd", "cicd", "github actions", "jenkins", "azure devops", "gitlab ci"],
            "containers": ["docker", "container", "containerized"],
            "automation": ["automation", "python", "bash", "powershell", "scripting"],
            "observability": ["prometheus", "grafana", "elk", "splunk", "opentelemetry", "logging", "monitoring"],
            "platform_engineering": ["platform engineering", "platform services", "developer platform", "internal developer platform"],
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
            "bi": ["power bi", "tableau", "looker", "dashboard", "reporting"],
            "analytics": ["data analysis", "analytics", "kpi", "trend analysis", "insights"],
            "database": ["mysql", "postgresql", "snowflake", "sql server", "bigquery"],
        },
        "preferred": {
            "cloud": ["aws", "azure", "gcp", "redshift", "athena"],
            "etl": ["etl", "data pipeline", "data modeling", "dbt"],
            "healthcare": ["healthcare", "claims", "ehr", "hipaa", "hedis", "cms"],
            "statistics": ["statistics", "regression", "forecasting", "a/b testing"],
        },
    },
    "software": {
        "core": {
            "programming": ["python", "java", "javascript", "typescript", "c#", "go", "ruby"],
            "frontend": ["react", "angular", "vue", "html", "css"],
            "backend": ["api", "rest", "graphql", "microservices", "node", "django", "flask", "spring"],
            "database": ["sql", "postgresql", "mysql", "mongodb", "redis"],
            "testing": ["unit testing", "integration testing", "pytest", "jest", "selenium"],
        },
        "preferred": {
            "cloud": ["aws", "azure", "gcp", "docker", "kubernetes"],
            "cicd": ["ci/cd", "github actions", "jenkins", "gitlab ci"],
            "agile": ["agile", "scrum", "jira"],
        },
    },
}

EQUIVALENCE_GROUPS = [
    ["eks", "aks", "gke", "kubernetes", "k8s"],
    ["terraform", "bicep", "cloudformation", "arm template"],
    ["github actions", "jenkins", "azure devops", "gitlab ci"],
    ["prometheus", "grafana", "elk", "splunk", "opentelemetry"],
    ["aws", "azure", "gcp"],
    ["power bi", "tableau", "looker"],
    ["postgresql", "mysql", "sql server", "bigquery", "snowflake"],
    ["pytorch", "tensorflow", "keras"],
    ["mlflow", "sagemaker", "vertex ai", "azure ml", "kubeflow"],
    ["openai", "llm", "large language model", "generative ai", "genai"],
]

STOPWORDS = {
    "about", "after", "also", "and", "are", "based", "been", "being", "can", "company",
    "data", "day", "days", "each", "for", "from", "have", "into", "job", "jobs", "more",
    "our", "role", "team", "than", "that", "the", "their", "this", "through", "with",
    "work", "working", "you", "your", "will",
}


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

    profile_terms = {
        "ai_ml": [
            "ai/ml", "machine learning", "ml engineer", "ai engineer", "artificial intelligence",
            "generative ai", "genai", "llm", "nlp", "computer vision", "mlops",
            "pytorch", "tensorflow", "model deployment",
        ],
        "platform": [
            "platform engineer", "devops", "sre", "infrastructure", "cloud engineer",
            "kubernetes", "terraform", "ci/cd",
        ],
        "data": [
            "data analyst", "business intelligence", "bi analyst", "healthcare analyst",
            "financial analyst", "sql", "power bi", "analytics",
        ],
        "software": [
            "software engineer", "developer", "frontend", "backend", "full stack",
            "react", "java", "javascript", "api",
        ],
    }

    scores = {
        profile: sum(1 for term in terms if term in combined)
        for profile, terms in profile_terms.items()
    }

    return max(scores, key=scores.get) if max(scores.values()) else "software"


def skill_group_match(resume_text: str, jd_text: str, skill_groups: dict) -> tuple[float, int, list, list, list]:
    matched = []
    missing = []
    partial = []
    score_units = 0.0

    for group_name, keywords in skill_groups.items():
        jd_needs_group = contains_any(jd_text, keywords)
        resume_has_group = contains_any(resume_text, keywords)

        if not jd_needs_group:
            continue

        if resume_has_group:
            matched.append(group_name)
            score_units += 1
            continue

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


def extract_keywords(text: str, limit: int = 25) -> list[str]:
    tokens = [
        token for token in re.findall(r"[a-z][a-z0-9+#./-]{2,}", normalize(text))
        if token not in STOPWORDS and len(token) <= 30
    ]
    counts = Counter(tokens)
    return [word for word, _ in counts.most_common(limit)]


def keyword_overlap(resume_text: str, jd_text: str) -> tuple[list[str], list[str]]:
    jd_keywords = extract_keywords(jd_text, limit=35)
    resume = normalize(resume_text)

    matched = [keyword for keyword in jd_keywords if keyword in resume]
    missing = [keyword for keyword in jd_keywords if keyword not in resume]

    return matched[:15], missing[:15]


def build_suggestions(missing_groups: list[str], missing_keywords: list[str], score: float) -> str:
    if score >= 70:
        return "Good fit. Tailor the resume summary and bullets toward the listed matched skills."

    focus_terms = missing_groups[:5] or missing_keywords[:5]
    if not focus_terms:
        return "Low ATS score. Improve role-title alignment and add measurable achievements from the job description."

    return "Low ATS score. Add truthful resume evidence for: " + ", ".join(focus_terms) + "."


def calculate_ats_score(resume_text: str, job: dict, target_role: str) -> dict:
    resume_text = normalize(resume_text)
    jd_text = normalize(
        " ".join(
            [
                job.get("job_role", ""),
                job.get("company", ""),
                job.get("description", ""),
                job.get("verified_page_text", ""),
            ]
        )
    )
    job_title = job.get("job_role", "")

    role_profile_name = detect_role_profile(target_role, job_title, jd_text)
    profile = ROLE_SKILL_PROFILES[role_profile_name]

    core_score_units, core_total, core_matched, core_partial, core_missing = skill_group_match(
        resume_text, jd_text, profile["core"]
    )
    preferred_score_units, preferred_total, preferred_matched, preferred_partial, preferred_missing = skill_group_match(
        resume_text, jd_text, profile["preferred"]
    )
    jd_matched, jd_missing = keyword_overlap(resume_text, jd_text)

    core_score = (core_score_units / core_total) * 45 if core_total else 0
    preferred_score = (preferred_score_units / preferred_total) * 20 if preferred_total else 0
    title_score = fuzz.token_set_ratio(normalize(target_role), normalize(job_title)) * 0.20
    jd_keyword_score = (len(jd_matched) / max(len(jd_matched) + len(jd_missing), 1)) * 15

    total_score = round(min(core_score + preferred_score + title_score + jd_keyword_score, 100), 2)
    matched_keywords = sorted(set(core_matched + preferred_matched + jd_matched))
    partial_keywords = sorted(set(core_partial + preferred_partial))
    missing_keywords = sorted(set(core_missing + preferred_missing + jd_missing))

    return {
        "ats_score": total_score,
        "role_profile": role_profile_name,
        "matched_keywords": matched_keywords,
        "partial_matches": partial_keywords,
        "missing_keywords": missing_keywords,
        "ats_suggestion": build_suggestions(missing_keywords, jd_missing, total_score),
    }
